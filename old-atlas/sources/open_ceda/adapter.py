from __future__ import annotations

import io
import json

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
from sources.open_ceda.normalizer import OpenCedaNormalizer
from sources.open_ceda.parser import OpenCedaParser, OpenCedaWorkbook


class OpenCedaAdapter(BaseAtlasSourceAdapter):
    def __init__(
        self,
        *,
        repository: AtlasRepository,
        storage: ObjectStorage,
        fetcher: HttpAssetFetcher | None = None,
        parser: OpenCedaParser | None = None,
        normalizer: OpenCedaNormalizer | None = None,
    ) -> None:
        super().__init__(repository=repository, storage=storage)
        self.fetcher = fetcher or HttpAssetFetcher()
        self.parser = parser or OpenCedaParser()
        self.normalizer = normalizer or OpenCedaNormalizer()
        self._release_year: int | None = None
        self._revision: str | None = None
        self._asset_url: str | None = None
        self._asset: FetchedAsset | None = None
        self._workbook: OpenCedaWorkbook | None = None

    async def check(self, context: PipelineContext) -> ChangeCheckResult:
        release_year = context.run.requested_reference_year or context.source.history.end_year
        if release_year is None:
            raise ValueError("Open CEDA manifest requires a release-year range")
        schema = context.source.history.schema_for(release_year)
        context.parser_version = schema.parser_version
        try:
            asset_url = str(context.source.history.release_pages[release_year])
        except KeyError as error:
            raise ValueError(f"Open CEDA release URL is missing for {release_year}") from error

        previous = await self.repository.last_source_revision(
            context.source.code,
            parser_version=context.effective_parser_version,
            mapping_version=context.source.adapter.mapping_version,
        )
        result = await self.fetcher.check(asset_url, previous)
        self._release_year = release_year
        self._revision = result.revision
        self._asset_url = asset_url
        context.source_dataset_version = f"CEDA {release_year}"
        context.metrics["release_year"] = release_year
        contextual = result.model_copy(
            update={
                "reason": (
                    f"Open CEDA {release_year} workbook changed"
                    if result.changed
                    else f"Open CEDA {release_year} workbook unchanged"
                )
            }
        )
        await self.repository.record_source_check(context.source.code, context.run.id, contextual)
        return contextual

    async def fetch(self, context: PipelineContext) -> FetchedAsset:
        del context
        if self._asset_url is None:
            raise ValueError("check must select an Open CEDA release before fetch")
        self._asset = await self.fetcher.fetch(self._asset_url)
        return self._asset

    async def parse(self, context: PipelineContext) -> tuple[ParsedRecord, ...]:
        if (
            context.fetched_asset is None
            or context.fetched_asset.local_path is None
            or self._release_year is None
        ):
            raise ValueError("Open CEDA parser requires a downloaded workbook and release year")
        self._workbook = self.parser.parse(
            context.fetched_asset.local_path,
            release_year=self._release_year,
        )
        context.source_published_at = self._workbook.published_at
        context.metrics.update(self.parser.metrics)
        parsed = tuple(
            [row.as_parsed_record() for row in self._workbook.factors]
            + [row.as_parsed_record() for row in self._workbook.parameters]
        )
        context.parsed_artifact = await self.storage.store_processing(
            source_code=context.source.code,
            version_key=self._version_key(context),
            layer="parsed",
            content=self._records_to_parquet(parsed),
            row_count=len(parsed),
            extension="parquet",
        )
        return parsed

    async def normalize(self, context: PipelineContext) -> tuple[CanonicalFactor, ...]:
        if context.raw_asset is None or self._workbook is None or self._revision is None:
            raise ValueError("Open CEDA workbook metadata is unavailable")
        factors, observations, metrics = self.normalizer.normalize(
            self._workbook.factors,
            self._workbook.parameters,
            raw=context.raw_asset,
            revision=self._revision,
            parser_version=context.effective_parser_version,
        )
        context.source_observations = observations
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
        findings = list(report.findings)
        zero_values = context.metrics.get("zero_value_factors", 0)
        if zero_values:
            findings.append(
                QualityFinding(
                    rule_code="open_ceda.zero_values",
                    severity=QualitySeverity.WARNING,
                    message=f"Open CEDA reports {zero_values} zero-valued factor cells",
                    details={"count": zero_values},
                )
            )
        return QualityReport(checked_records=report.checked_records, findings=tuple(findings))

    async def version(self, context: PipelineContext) -> str:
        try:
            return await super().version(context)
        finally:
            self._remove_temporary_asset()

    async def close(self) -> None:
        self._remove_temporary_asset()
        await self.fetcher.close()

    def _version_key(self, context: PipelineContext) -> str:
        if context.raw_asset is None or self._release_year is None:
            raise ValueError("Open CEDA raw metadata is unavailable")
        return f"ceda-{self._release_year}-{context.raw_asset.sha256[:12]}"

    def _remove_temporary_asset(self) -> None:
        if self._asset is not None and self._asset.local_path is not None:
            self._asset.local_path.unlink(missing_ok=True)

    @staticmethod
    def _records_to_parquet(records: tuple[ParsedRecord, ...]) -> bytes:
        payloads = [
            {
                "source_sheet": record.source_sheet,
                "source_table": record.source_table,
                "source_row": record.source_row,
                "payload": json.dumps(record.data, sort_keys=True),
            }
            for record in records
        ]
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
