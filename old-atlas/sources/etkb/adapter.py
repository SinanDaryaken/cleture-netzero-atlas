from __future__ import annotations

import hashlib
import io
import json
from datetime import UTC, datetime, time
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
from atlas.infrastructure.http import HttpAssetFetcher
from atlas.ingestion.base import BaseAtlasSourceAdapter
from atlas.ports.storage import ObjectStorage
from sources.etkb.normalizer import EtkbNormalizer
from sources.etkb.parser import EtkbDocument, EtkbParser


class EtkbAdapter(BaseAtlasSourceAdapter):
    def __init__(
        self,
        *,
        repository: AtlasRepository,
        storage: ObjectStorage,
        fetcher: HttpAssetFetcher | None = None,
        parser: EtkbParser | None = None,
        normalizer: EtkbNormalizer | None = None,
    ) -> None:
        super().__init__(repository=repository, storage=storage)
        self.fetcher = fetcher or HttpAssetFetcher()
        self.parser = parser or EtkbParser()
        self.normalizer = normalizer or EtkbNormalizer(
            Path(__file__).with_name("mappings.yaml")
        )
        self._asset: FetchedAsset | None = None
        self._document: EtkbDocument | None = None
        self._revision: str | None = None

    async def check(self, context: PipelineContext) -> ChangeCheckResult:
        target_year = context.run.requested_reference_year or context.source.history.end_year
        if target_year is None:
            raise ValueError("ETKB manifest requires an end year")
        asset_url = context.source.history.release_pages[target_year]
        self._asset = await self.fetcher.fetch(str(asset_url))
        if self._asset.local_path is None:
            raise ValueError("ETKB change detection requires a local PDF path")
        self._document = self.parser.parse(self._asset.local_path)
        if self._document.reference_year != target_year:
            raise ValueError(
                f"ETKB PDF year {self._document.reference_year} does not match {target_year}"
            )
        self._revision = hashlib.sha256(self._asset.local_path.read_bytes()).hexdigest()
        context.source_dataset_version = (
            f"{target_year}-r{self._document.calculation_revision}"
        )
        context.parser_version = context.source.history.schema_for(target_year).parser_version
        context.source_published_at = datetime.combine(
            self._document.published_on, time.min, tzinfo=UTC
        )
        context.metrics.update(self.parser.metrics)
        previous = await self.repository.last_source_revision(
            context.source.code,
            reference_year=target_year,
            parser_version=context.effective_parser_version,
            mapping_version=context.source.adapter.mapping_version,
        )
        changed = previous != self._revision
        result = ChangeCheckResult(
            changed=changed,
            revision=self._revision if changed else None,
            reason=(
                f"ETKB {target_year} annual electricity PDF changed"
                if changed
                else f"ETKB {target_year} annual electricity PDF unchanged"
            ),
        )
        await self.repository.record_source_check(context.source.code, context.run.id, result)
        return result

    async def fetch(self, context: PipelineContext) -> FetchedAsset:
        del context
        if self._asset is None:
            raise ValueError("check must download the ETKB PDF before fetch")
        return self._asset

    async def parse(self, context: PipelineContext) -> tuple[ParsedRecord, ...]:
        if context.raw_asset is None or self._document is None:
            raise ValueError("ETKB parsed document is unavailable")
        parsed = self._document.parsed_records
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
        if context.raw_asset is None or self._document is None:
            raise ValueError("ETKB release metadata is unavailable")
        factors, metrics = self.normalizer.normalize(
            self._document.rows,
            raw=context.raw_asset,
            release_year=self._document.reference_year,
            calculation_revision=self._document.calculation_revision,
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
        if context.raw_asset is None or self._document is None:
            raise ValueError("ETKB raw metadata is unavailable")
        return (
            f"{self._document.reference_year}-r{self._document.calculation_revision}-"
            f"{context.raw_asset.sha256[:12]}"
        )

    def _remove_temporary_asset(self) -> None:
        if self._asset is not None and self._asset.local_path is not None:
            self._asset.local_path.unlink(missing_ok=True)

    @staticmethod
    def _records_to_parquet(records: tuple[ParsedRecord, ...]) -> bytes:
        frame = pl.DataFrame(
            [
                {
                    "source_sheet": record.source_sheet,
                    "source_table": record.source_table,
                    "source_row": record.source_row,
                    "payload": json.dumps(record.data, sort_keys=True),
                }
                for record in records
            ],
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
