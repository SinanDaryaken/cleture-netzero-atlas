from __future__ import annotations

import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from atlas.domain.enums import QualitySeverity
from atlas.domain.models import (
    CanonicalFactor,
    ChangeCheckResult,
    FetchedAsset,
    ParsedRecord,
    PipelineContext,
    QualityFinding,
    QualityReport,
)
from atlas.infrastructure.database.repositories import AtlasRepository
from atlas.infrastructure.http import HttpAssetFetcher
from atlas.ingestion.base import BaseAtlasSourceAdapter
from atlas.ports.storage import ObjectStorage
from sources.oekobaudat.normalizer import OekobaudatNormalizer
from sources.oekobaudat.parser import OekobaudatParser, OekobaudatRow


class OekobaudatAdapter(BaseAtlasSourceAdapter):
    def __init__(
        self,
        *,
        repository: AtlasRepository,
        storage: ObjectStorage,
        fetcher: HttpAssetFetcher | None = None,
        parser: OekobaudatParser | None = None,
        normalizer: OekobaudatNormalizer | None = None,
    ) -> None:
        super().__init__(repository=repository, storage=storage)
        self.fetcher = fetcher or HttpAssetFetcher()
        self.parser = parser or OekobaudatParser()
        self.normalizer = normalizer or OekobaudatNormalizer(
            Path(__file__).with_name("mappings.yaml")
        )
        self._asset: FetchedAsset | None = None
        self._rows: tuple[OekobaudatRow, ...] = ()
        self._revision: str | None = None

    async def check(self, context: PipelineContext) -> ChangeCheckResult:
        endpoint = context.source.history.snapshot_endpoints["current_export"]
        self._asset = await self.fetcher.fetch(str(endpoint))
        if self._asset.local_path is None:
            raise ValueError("ÖKOBAUDAT change detection requires a local CSV path")
        self._revision = hashlib.sha256(self._asset.local_path.read_bytes()).hexdigest()
        dataset_version = context.source.history.snapshot_parameters["dataset_version"]
        context.source_dataset_version = dataset_version
        context.source_published_at = datetime.fromisoformat(
            context.source.history.snapshot_parameters["release_published_at"]
        ).replace(tzinfo=UTC)
        previous = await self.repository.last_source_revision(
            context.source.code,
            parser_version=context.effective_parser_version,
            mapping_version=context.source.adapter.mapping_version,
        )
        changed = previous != self._revision
        result = ChangeCheckResult(
            changed=changed,
            revision=self._revision if changed else None,
            reason=(
                f"ÖKOBAUDAT {dataset_version} CSV snapshot changed"
                if changed
                else f"ÖKOBAUDAT {dataset_version} CSV snapshot unchanged"
            ),
        )
        await self.repository.record_source_check(context.source.code, context.run.id, result)
        return result

    async def fetch(self, context: PipelineContext) -> FetchedAsset:
        del context
        if self._asset is None:
            raise ValueError("check must download the ÖKOBAUDAT CSV before fetch")
        return self._asset

    async def parse(self, context: PipelineContext) -> tuple[ParsedRecord, ...]:
        if context.fetched_asset is None or context.fetched_asset.local_path is None:
            raise ValueError("ÖKOBAUDAT parser requires the local CSV path")
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
        if context.raw_asset is None:
            raise ValueError("ÖKOBAUDAT raw asset is unavailable")
        dataset_version = context.source.history.snapshot_parameters["dataset_version"]
        factors, metrics = self.normalizer.normalize(
            self._rows,
            raw=context.raw_asset,
            dataset_version=dataset_version,
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

    async def validate(self, context: PipelineContext) -> QualityReport:
        report = await super().validate(context)
        missing = context.metrics.get("excluded_missing_total_gwp", 0)
        missing_reference = context.metrics.get("excluded_missing_reference", 0)
        if not missing and not missing_reference:
            return report
        return QualityReport(
            checked_records=report.checked_records,
            findings=(
                *report.findings,
                QualityFinding(
                    rule_code="oekobaudat.missing_total_gwp",
                    severity=QualitySeverity.WARNING,
                    message=(
                        "ÖKOBAUDAT rows without a total GWP result or declared reference "
                        f"were excluded: {missing + missing_reference}"
                    ),
                    details={
                        "missing_total_gwp": missing,
                        "missing_reference": missing_reference,
                    },
                ),
            ),
        )

    async def version(self, context: PipelineContext) -> str:
        try:
            return await super().version(context)
        finally:
            self._remove_temporary_asset()

    async def close(self) -> None:
        self._remove_temporary_asset()
        await self.fetcher.close()

    def _version_key(self, context: PipelineContext) -> str:
        if context.raw_asset is None:
            raise ValueError("ÖKOBAUDAT raw metadata is unavailable")
        version = context.source.history.snapshot_parameters["dataset_version"]
        return f"{version}-{context.raw_asset.sha256[:12]}"

    def _remove_temporary_asset(self) -> None:
        if self._asset is not None and self._asset.local_path is not None:
            self._asset.local_path.unlink(missing_ok=True)

    @staticmethod
    def _rows_to_parquet(rows: tuple[OekobaudatRow, ...]) -> bytes:
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
