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
from atlas.infrastructure.http import HttpAssetFetcher
from atlas.ingestion.base import BaseAtlasSourceAdapter
from atlas.ports.storage import ObjectStorage
from sources.defra.normalizer import DefraNormalizer
from sources.defra.parser import DefraParser, DefraRow


class DefraAdapter(BaseAtlasSourceAdapter):
    def __init__(
        self,
        *,
        repository: AtlasRepository,
        storage: ObjectStorage,
        fetcher: HttpAssetFetcher | None = None,
        parser: DefraParser | None = None,
        normalizer: DefraNormalizer | None = None,
    ) -> None:
        super().__init__(repository=repository, storage=storage)
        self.fetcher = fetcher or HttpAssetFetcher()
        self.parser = parser or DefraParser()
        self.normalizer = normalizer or DefraNormalizer(Path(__file__).with_name("mappings.yaml"))
        self._asset_url: str | None = None
        self._release_year: int | None = None
        self._rows: tuple[DefraRow, ...] = ()

    async def check(self, context: PipelineContext) -> ChangeCheckResult:
        target_year = context.run.requested_reference_year
        release_page = (
            context.source.history.release_pages.get(target_year)
            if target_year is not None
            else None
        )
        self._asset_url, self._release_year = await self.fetcher.resolve_defra_release(
            str(context.source.location.landing_page),
            reference_year=target_year,
            release_page=str(release_page) if release_page is not None else None,
        )
        context.source_dataset_version = str(self._release_year)
        context.parser_version = context.source.history.schema_for(
            self._release_year
        ).parser_version
        context.metrics["release_year"] = self._release_year
        previous = await self.repository.last_source_revision(
            context.source.code,
            reference_year=self._release_year,
            parser_version=context.effective_parser_version,
            mapping_version=context.source.adapter.mapping_version,
        )
        result = await self.fetcher.check(self._asset_url, previous)
        await self.repository.record_source_check(context.source.code, context.run.id, result)
        return result

    async def fetch(self, context: PipelineContext) -> FetchedAsset:
        del context
        if self._asset_url is None:
            raise ValueError("check must resolve the asset before fetch")
        return await self.fetcher.fetch(self._asset_url)

    async def parse(self, context: PipelineContext) -> tuple[ParsedRecord, ...]:
        if context.fetched_asset is None or context.fetched_asset.local_path is None:
            raise ValueError("DEFRA parser requires a local workbook path")
        if context.raw_asset is None:
            raise ValueError("raw asset must be stored before parsing")
        self._rows = self.parser.parse(context.fetched_asset.local_path)
        parsed = tuple(row.as_parsed_record() for row in self._rows)
        content = self._rows_to_parquet(self._rows)
        version_key = self._version_key(context)
        context.parsed_artifact = await self.storage.store_processing(
            source_code=context.source.code,
            version_key=version_key,
            layer="parsed",
            content=content,
            row_count=len(parsed),
            extension="parquet",
        )
        return parsed

    async def normalize(self, context: PipelineContext) -> tuple[CanonicalFactor, ...]:
        if context.raw_asset is None:
            raise ValueError("raw asset must be stored before normalization")
        if self._release_year is None:
            raise ValueError("release year is unavailable")
        factors, metrics = self.normalizer.normalize(
            self._rows,
            raw=context.raw_asset,
            release_year=self._release_year,
            parser_version=context.effective_parser_version,
        )
        context.metrics.update(metrics)
        content = self._factors_to_parquet(factors)
        context.normalized_artifact = await self.storage.store_processing(
            source_code=context.source.code,
            version_key=self._version_key(context),
            layer="normalized",
            content=content,
            row_count=len(factors),
            extension="parquet",
        )
        return factors

    async def version(self, context: PipelineContext) -> str:
        try:
            return await super().version(context)
        finally:
            if context.fetched_asset is not None and context.fetched_asset.local_path is not None:
                context.fetched_asset.local_path.unlink(missing_ok=True)

    async def close(self) -> None:
        await self.fetcher.close()

    def _version_key(self, context: PipelineContext) -> str:
        if context.raw_asset is None or self._release_year is None:
            raise ValueError("release metadata is unavailable")
        return f"{self._release_year}-{context.raw_asset.sha256[:12]}"

    @staticmethod
    def _rows_to_parquet(rows: tuple[DefraRow, ...]) -> bytes:
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
            payload["gases"] = json.dumps(payload["gases"], sort_keys=True)
            payload["origin_geography"] = json.dumps(payload["origin_geography"], sort_keys=True)
            payload["applicable_geographies"] = json.dumps(
                payload["applicable_geographies"], sort_keys=True
            )
            payload["methodology"] = json.dumps(payload["methodology"], sort_keys=True)
            payload["provenance"] = json.dumps(payload["provenance"], sort_keys=True)
            payload["component_provenance"] = json.dumps(
                payload["component_provenance"], sort_keys=True
            )
            payloads.append(payload)
        frame = pl.DataFrame(payloads, infer_schema_length=None, strict=False)
        buffer = io.BytesIO()
        frame.write_parquet(buffer)
        return buffer.getvalue()
