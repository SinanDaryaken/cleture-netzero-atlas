from __future__ import annotations

import io
import json
from pathlib import Path

import polars as pl

from atlas.domain.models import (
    CanonicalFactor,
    ChangeCheckResult,
    FetchedAsset,
    ParsedRecord,
    PipelineContext,
)
from atlas.infrastructure.database.repositories import AtlasRepository
from atlas.infrastructure.http import AibRelease, HttpAssetFetcher
from atlas.ingestion.base import BaseAtlasSourceAdapter
from atlas.ports.storage import ObjectStorage
from sources.aib.normalizer import AibNormalizer
from sources.aib.parser import AibParser, AibRow


class AibAdapter(BaseAtlasSourceAdapter):
    def __init__(
        self,
        *,
        repository: AtlasRepository,
        storage: ObjectStorage,
        fetcher: HttpAssetFetcher | None = None,
        parser: AibParser | None = None,
        normalizer: AibNormalizer | None = None,
    ) -> None:
        super().__init__(repository=repository, storage=storage)
        self.fetcher = fetcher or HttpAssetFetcher()
        self.parser = parser or AibParser()
        self.normalizer = normalizer or AibNormalizer(Path(__file__).with_name("mappings.yaml"))
        self._release: AibRelease | None = None
        self._asset: FetchedAsset | None = None
        self._rows: tuple[AibRow, ...] = ()

    async def check(self, context: PipelineContext) -> ChangeCheckResult:
        target_year = context.run.requested_reference_year
        landing_page = context.source.location.landing_page
        if target_year is not None:
            landing_page = context.source.history.release_pages[target_year]
        self._release = await self.fetcher.resolve_aib_release(
            str(landing_page), reference_year=target_year
        )
        context.source_dataset_version = f"{self._release.year}-v{self._release.version}"
        context.parser_version = context.source.history.schema_for(
            self._release.year
        ).parser_version
        context.source_published_at = self._release.published_on
        context.metrics["release_year"] = self._release.year
        previous = await self.repository.last_source_revision(
            context.source.code,
            reference_year=self._release.year,
            parser_version=context.effective_parser_version,
            mapping_version=context.source.adapter.mapping_version,
        )
        result = await self.fetcher.check(self._release.asset_url, previous)
        await self.repository.record_source_check(context.source.code, context.run.id, result)
        return result

    async def fetch(self, context: PipelineContext) -> FetchedAsset:
        del context
        if self._release is None:
            raise ValueError("check must resolve the AIB release before fetch")
        self._asset = await self.fetcher.fetch(self._release.asset_url)
        return self._asset

    async def parse(self, context: PipelineContext) -> tuple[ParsedRecord, ...]:
        if context.fetched_asset is None or context.fetched_asset.local_path is None:
            raise ValueError("AIB parser requires a local workbook path")
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
        if context.raw_asset is None or self._release is None:
            raise ValueError("AIB release metadata is unavailable")
        factors, metrics = self.normalizer.normalize(
            self._rows,
            raw=context.raw_asset,
            release_year=self._release.year,
            release_version=self._release.version,
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
        if context.raw_asset is None or self._release is None:
            raise ValueError("AIB release metadata is unavailable")
        return f"{self._release.year}-v{self._release.version}-{context.raw_asset.sha256[:12]}"

    def _remove_temporary_asset(self) -> None:
        if self._asset is not None and self._asset.local_path is not None:
            self._asset.local_path.unlink(missing_ok=True)

    @staticmethod
    def _rows_to_parquet(rows: tuple[AibRow, ...]) -> bytes:
        payloads = []
        for row in rows:
            payload = row.model_dump(mode="json")
            payload["shares"] = json.dumps(payload["shares"], sort_keys=True)
            payloads.append(payload)
        frame = pl.DataFrame(payloads, infer_schema_length=None, strict=False)
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
