from __future__ import annotations

import io
import json
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
from atlas.infrastructure.http import AdemeRelease, HttpAssetFetcher
from atlas.ingestion.base import BaseAtlasSourceAdapter
from atlas.ports.storage import ObjectStorage
from sources.ademe.normalizer import AdemeNormalizer
from sources.ademe.parser import AdemeParser, AdemeRow


class AdemeAdapter(BaseAtlasSourceAdapter):
    def __init__(
        self,
        *,
        repository: AtlasRepository,
        storage: ObjectStorage,
        fetcher: HttpAssetFetcher | None = None,
        parser: AdemeParser | None = None,
        normalizer: AdemeNormalizer | None = None,
    ) -> None:
        super().__init__(repository=repository, storage=storage)
        self.fetcher = fetcher or HttpAssetFetcher()
        self.parser = parser or AdemeParser()
        self.normalizer = normalizer or AdemeNormalizer(Path(__file__).with_name("mappings.yaml"))
        self._release: AdemeRelease | None = None
        self._asset: FetchedAsset | None = None
        self._rows: tuple[AdemeRow, ...] = ()

    async def check(self, context: PipelineContext) -> ChangeCheckResult:
        api_url = context.source.location.api_url
        if api_url is None:
            raise ValueError("ADEME manifest requires a Data Fair API URL")
        self._release = await self.fetcher.resolve_ademe_release(str(api_url))
        context.source_dataset_version = self._release.version
        previous = await self.repository.last_source_revision(
            context.source.code,
            parser_version=context.effective_parser_version,
            mapping_version=context.source.adapter.mapping_version,
        )
        changed = self._release.revision != previous
        result = ChangeCheckResult(
            changed=changed,
            revision=self._release.revision if changed else None,
            last_modified=self._release.source_updated_at,
            reason=(
                f"Base Carbone V{self._release.version} changed ({self._release.row_count} records)"
                if changed
                else f"Base Carbone V{self._release.version} unchanged "
                f"({self._release.row_count} records)"
            ),
        )
        context.metrics["reported_rows"] = self._release.row_count
        await self.repository.record_source_check(context.source.code, context.run.id, result)
        return result

    async def fetch(self, context: PipelineContext) -> FetchedAsset:
        del context
        if self._release is None:
            raise ValueError("check must resolve the ADEME release before fetch")
        self._asset = await self.fetcher.fetch(self._release.asset_url)
        return self._asset

    async def parse(self, context: PipelineContext) -> tuple[ParsedRecord, ...]:
        if context.fetched_asset is None or context.fetched_asset.local_path is None:
            raise ValueError("ADEME parser requires a local CSV path")
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
            raise ValueError("ADEME release metadata is unavailable")
        factors, metrics = self.normalizer.normalize(
            self._rows,
            raw=context.raw_asset,
            dataset_version=self._release.version,
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
        unmapped = context.metrics.get("excluded_unmapped_geography", 0)
        if not unmapped:
            return report
        return QualityReport(
            checked_records=report.checked_records,
            findings=(
                *report.findings,
                QualityFinding(
                    rule_code="geography.source_values_unmapped",
                    severity=QualitySeverity.REVIEW_REQUIRED,
                    message=(
                        f"{unmapped} ADEME factors have country labels without "
                        "approved ISO mappings"
                    ),
                    details={"excluded_factor_count": unmapped},
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
        if context.raw_asset is None or self._release is None:
            raise ValueError("ADEME release metadata is unavailable")
        return f"v{self._release.version}-{context.raw_asset.sha256[:12]}"

    def _remove_temporary_asset(self) -> None:
        if self._asset is not None and self._asset.local_path is not None:
            self._asset.local_path.unlink(missing_ok=True)

    @staticmethod
    def _rows_to_parquet(rows: tuple[AdemeRow, ...]) -> bytes:
        payloads = []
        for row in rows:
            payload = row.model_dump(mode="json")
            payload["additional_gases"] = json.dumps(payload["additional_gases"], sort_keys=True)
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
