from __future__ import annotations

import io
import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from atlas.config import get_settings
from atlas.domain.models import (
    CanonicalFactor,
    ChangeCheckResult,
    FetchedAsset,
    ParsedRecord,
    PipelineContext,
)
from atlas.infrastructure.database.repositories import AtlasRepository
from atlas.infrastructure.http import HttpAssetFetcher
from atlas.ingestion.base import BaseAtlasSourceAdapter
from atlas.ports.storage import ObjectStorage
from sources.ipcc.normalizer import IpccNormalizer
from sources.ipcc.parser import IpccParser, IpccRow


class IpccAdapter(BaseAtlasSourceAdapter):
    def __init__(
        self,
        *,
        repository: AtlasRepository,
        storage: ObjectStorage,
        fetcher: HttpAssetFetcher | None = None,
        parser: IpccParser | None = None,
        normalizer: IpccNormalizer | None = None,
        local_asset_root: Path | None = None,
    ) -> None:
        super().__init__(repository=repository, storage=storage)
        self.fetcher = fetcher or HttpAssetFetcher()
        self.parser = parser or IpccParser()
        self.normalizer = normalizer or IpccNormalizer(Path(__file__).with_name("mappings.yaml"))
        self.local_asset_root = local_asset_root or get_settings().local_source_asset_root
        self._asset: FetchedAsset | None = None
        self._asset_url: str | None = None
        self._local_asset: Path | None = None
        self._revision: str | None = None
        self._rows: tuple[IpccRow, ...] = ()

    async def check(self, context: PipelineContext) -> ChangeCheckResult:
        self._asset_url = str(
            context.source.location.download_url or context.source.location.landing_page
        )
        candidate = (
            self.local_asset_root / "ipcc" / "ipcc-efdb.xlsx"
            if self.local_asset_root is not None
            else None
        )
        if candidate is not None and candidate.is_file():
            self._local_asset = candidate
            self._revision = self.fetcher._xlsx_sheet_revision(candidate.read_bytes())
            row_count = len(self.parser.parse(candidate))
        else:
            self._asset, self._revision, row_count = await self.fetcher.fetch_ipcc_export(
                str(context.source.location.landing_page)
            )
        previous = await self.repository.last_source_revision(
            context.source.code,
            parser_version=context.effective_parser_version,
            mapping_version=context.source.adapter.mapping_version,
        )
        changed = self._revision != previous
        result = ChangeCheckResult(
            changed=changed,
            revision=self._revision if changed else None,
            reason=(
                f"EFDB worksheet changed ({row_count} records)"
                if changed
                else f"EFDB worksheet unchanged ({row_count} records)"
            ),
        )
        context.metrics["reported_rows"] = row_count
        await self.repository.record_source_check(context.source.code, context.run.id, result)
        return result

    async def fetch(self, context: PipelineContext) -> FetchedAsset:
        del context
        if self._local_asset is not None:
            if self._asset_url is None:
                raise ValueError("IPCC source URL is unavailable")
            temporary = tempfile.NamedTemporaryFile(
                prefix="atlas-ipcc-", suffix=".xlsx", delete=False
            )
            temporary.close()
            path = Path(temporary.name)
            shutil.copyfile(self._local_asset, path)
            self._asset = FetchedAsset(
                filename=self._local_asset.name,
                local_path=path,
                source_url=self._asset_url,
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                downloaded_at=datetime.now(UTC),
                metadata={"acquisition": "local_source_asset_root"},
            )
        if self._asset is None or self._revision is None:
            raise ValueError("check must export the IPCC workbook before fetch")
        return self._asset

    async def parse(self, context: PipelineContext) -> tuple[ParsedRecord, ...]:
        if context.fetched_asset is None or context.fetched_asset.local_path is None:
            raise ValueError("IPCC parser requires a local workbook path")
        if context.raw_asset is None:
            raise ValueError("raw asset must be stored before parsing")
        self._rows = self.parser.parse(context.fetched_asset.local_path)
        context.metrics.update(self.parser.metrics)
        parsed = tuple(row.as_parsed_record() for row in self._rows)
        context.parsed_artifact = await self.storage.store_processing(
            source_code=context.source.code,
            version_key=self._version_key(context),
            layer="parsed",
            content=self._rows_to_parquet(self._rows),
            row_count=len(parsed),
            extension="parquet",
        )
        return parsed

    async def normalize(self, context: PipelineContext) -> tuple[CanonicalFactor, ...]:
        if context.raw_asset is None or self._revision is None:
            raise ValueError("IPCC release metadata is unavailable")
        factors, metrics = self.normalizer.normalize(
            self._rows,
            raw=context.raw_asset,
            dataset_revision=self._revision,
            parser_version=context.effective_parser_version,
        )
        context.metrics.update(metrics)
        context.normalized_artifact = await self.storage.store_processing(
            source_code=context.source.code,
            version_key=self._version_key(context),
            layer="normalized",
            content=self._factors_to_parquet(factors),
            row_count=len(factors),
            extension="parquet",
        )
        return factors

    async def version(self, context: PipelineContext) -> str:
        try:
            return await super().version(context)
        finally:
            self._remove_temporary_asset()

    async def close(self) -> None:
        self._remove_temporary_asset()
        await self.fetcher.close()

    def _version_key(self, context: PipelineContext) -> str:
        if context.raw_asset is None or self._revision is None:
            raise ValueError("IPCC release metadata is unavailable")
        return f"efdb-{self._revision[:12]}-{context.raw_asset.sha256[:12]}"

    def _remove_temporary_asset(self) -> None:
        if self._asset is not None and self._asset.local_path is not None:
            self._asset.local_path.unlink(missing_ok=True)

    @staticmethod
    def _rows_to_parquet(rows: tuple[IpccRow, ...]) -> bytes:
        frame = pl.DataFrame(
            [row.model_dump(mode="json") for row in rows],
            infer_schema_length=None,
            strict=False,
        )
        buffer = io.BytesIO()
        frame.write_parquet(buffer)
        return buffer.getvalue()

    @staticmethod
    def _factors_to_parquet(factors: tuple[CanonicalFactor, ...]) -> bytes:
        payloads = []
        for factor in factors:
            payload = factor.model_dump(mode="json")
            for key in (
                "gases",
                "origin_geography",
                "applicable_geographies",
                "methodology",
                "provenance",
                "component_provenance",
            ):
                payload[key] = json.dumps(payload[key], sort_keys=True)
            payloads.append(payload)
        frame = pl.DataFrame(payloads, infer_schema_length=None, strict=False)
        buffer = io.BytesIO()
        frame.write_parquet(buffer)
        return buffer.getvalue()
