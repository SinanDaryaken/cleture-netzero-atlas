from __future__ import annotations

import io
import json

import polars as pl

from atlas.config import get_settings
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
from atlas.infrastructure.http import EmberSnapshot, HttpAssetFetcher
from atlas.ingestion.base import BaseAtlasSourceAdapter
from atlas.ingestion.errors import PermanentIngestionError
from atlas.ports.storage import ObjectStorage
from sources.ember.normalizer import EmberNormalizer
from sources.ember.parser import EmberParser, EmberRow


class EmberAdapter(BaseAtlasSourceAdapter):
    def __init__(
        self,
        *,
        repository: AtlasRepository,
        storage: ObjectStorage,
        fetcher: HttpAssetFetcher | None = None,
        parser: EmberParser | None = None,
        normalizer: EmberNormalizer | None = None,
        api_key: str | None = None,
    ) -> None:
        super().__init__(repository=repository, storage=storage)
        self.fetcher = fetcher or HttpAssetFetcher()
        self.parser = parser or EmberParser()
        self.normalizer = normalizer or EmberNormalizer()
        configured = get_settings().ember_api_key
        self.api_key = api_key or (configured.get_secret_value() if configured else None)
        self._snapshot: EmberSnapshot | None = None
        self._rows: tuple[EmberRow, ...] = ()

    async def check(self, context: PipelineContext) -> ChangeCheckResult:
        if not self.api_key:
            raise PermanentIngestionError("ATLAS_EMBER_API_KEY is required")
        endpoint = context.source.history.snapshot_endpoints["yearly_carbon_intensity"]
        parameters = context.source.history.snapshot_parameters
        self._snapshot = await self.fetcher.fetch_ember_time_series(
            str(endpoint),
            api_key=self.api_key,
            start_date=parameters["start_date"],
            end_date=parameters["end_date"],
        )
        context.source_dataset_version = f"carbon-intensity-through-{self._snapshot.maximum_year}"
        context.metrics.update(
            {
                "reported_rows": self._snapshot.row_count,
                "minimum_reference_year": self._snapshot.minimum_year,
                "maximum_reference_year": self._snapshot.maximum_year,
            }
        )
        previous = await self.repository.last_source_revision(
            context.source.code,
            parser_version=context.effective_parser_version,
            mapping_version=context.source.adapter.mapping_version,
        )
        changed = self._snapshot.revision != previous
        result = ChangeCheckResult(
            changed=changed,
            revision=self._snapshot.revision if changed else None,
            reason=(
                f"Ember time series changed ({self._snapshot.row_count} records)"
                if changed
                else f"Ember time series unchanged ({self._snapshot.row_count} records)"
            ),
        )
        await self.repository.record_source_check(context.source.code, context.run.id, result)
        return result

    async def fetch(self, context: PipelineContext) -> FetchedAsset:
        del context
        if self._snapshot is None:
            raise ValueError("check must fetch the Ember snapshot before fetch")
        return self._snapshot.asset

    async def parse(self, context: PipelineContext) -> tuple[ParsedRecord, ...]:
        if context.fetched_asset is None or context.fetched_asset.content is None:
            raise ValueError("Ember parser requires the fetched JSON response")
        self._rows = self.parser.parse(context.fetched_asset.content)
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
        if context.raw_asset is None or self._snapshot is None:
            raise ValueError("Ember snapshot metadata is unavailable")
        factors, metrics = self.normalizer.normalize(
            self._rows,
            raw=context.raw_asset,
            dataset_revision=self._snapshot.revision,
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
        findings = list(report.findings)
        for metric, message in (
            ("excluded_unmapped_geography", "Ember geographies require mapping"),
            ("negative_reference_values", "Ember reported negative intensity values"),
        ):
            count = context.metrics.get(metric, 0)
            if count:
                findings.append(
                    QualityFinding(
                        rule_code=f"ember.{metric}",
                        severity=QualitySeverity.REVIEW_REQUIRED,
                        message=f"{message}: {count}",
                        details={"count": count},
                    )
                )
        return QualityReport(checked_records=report.checked_records, findings=tuple(findings))

    async def close(self) -> None:
        await self.fetcher.close()

    def _version_key(self, context: PipelineContext) -> str:
        if context.raw_asset is None or self._snapshot is None:
            raise ValueError("Ember snapshot metadata is unavailable")
        return f"through-{self._snapshot.maximum_year}-{context.raw_asset.sha256[:12]}"

    @staticmethod
    def _rows_to_parquet(rows: tuple[EmberRow, ...]) -> bytes:
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
