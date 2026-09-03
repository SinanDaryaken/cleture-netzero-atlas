from __future__ import annotations

import io
import json
from datetime import UTC, datetime
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
from sources.ghg_protocol.normalizer import GhgProtocolNormalizer
from sources.ghg_protocol.parser import GhgProtocolDocument, GhgProtocolParser


class GhgProtocolAdapter(BaseAtlasSourceAdapter):
    VERSION = "2.0"

    def __init__(
        self,
        *,
        repository: AtlasRepository,
        storage: ObjectStorage,
        fetcher: HttpAssetFetcher | None = None,
        parser: GhgProtocolParser | None = None,
        normalizer: GhgProtocolNormalizer | None = None,
    ) -> None:
        super().__init__(repository=repository, storage=storage)
        self.fetcher = fetcher or HttpAssetFetcher()
        self.parser = parser or GhgProtocolParser()
        self.normalizer = normalizer or GhgProtocolNormalizer(
            Path(__file__).with_name("mappings.yaml")
        )
        self._asset: FetchedAsset | None = None
        self._document: GhgProtocolDocument | None = None

    async def check(self, context: PipelineContext) -> ChangeCheckResult:
        download_url = context.source.location.download_url
        if download_url is None:
            raise ValueError("GHG Protocol manifest requires an official workbook URL")
        context.source_dataset_version = self.VERSION
        context.source_published_at = datetime(2024, 3, 13, tzinfo=UTC)
        previous = await self.repository.last_source_revision(
            context.source.code,
            parser_version=context.effective_parser_version,
            mapping_version=context.source.adapter.mapping_version,
        )
        result = await self.fetcher.check(str(download_url), previous)
        await self.repository.record_source_check(context.source.code, context.run.id, result)
        return result

    async def fetch(self, context: PipelineContext) -> FetchedAsset:
        download_url = context.source.location.download_url
        if download_url is None:
            raise ValueError("GHG Protocol manifest requires an official workbook URL")
        self._asset = await self.fetcher.fetch(str(download_url))
        return self._asset

    async def parse(self, context: PipelineContext) -> tuple[ParsedRecord, ...]:
        if context.fetched_asset is None or context.fetched_asset.local_path is None:
            raise ValueError("GHG Protocol parser requires a local workbook path")
        if context.raw_asset is None:
            raise ValueError("raw asset must be stored before parsing")
        self._document = self.parser.parse(context.fetched_asset.local_path)
        context.metrics.update(self.parser.metrics)
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
            raise ValueError("GHG Protocol parsed workbook is unavailable")
        factors, observations, metrics = self.normalizer.normalize(
            self._document.factors,
            self._document.observations,
            raw=context.raw_asset,
            version=self._document.version,
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
            raise ValueError("GHG Protocol raw metadata is unavailable")
        return f"v{self.VERSION}-{context.raw_asset.sha256[:12]}"

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
