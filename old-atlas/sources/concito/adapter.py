from __future__ import annotations

import asyncio
import hashlib
import io
import json
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

import httpx
import polars as pl
from bs4 import BeautifulSoup

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
from atlas.ingestion.errors import RetryableIngestionError
from atlas.ports.storage import ObjectStorage
from sources.concito.normalizer import ConcitoNormalizer
from sources.concito.parser import ConcitoParser, ConcitoRow


class ConcitoAdapter(BaseAtlasSourceAdapter):
    detail_concurrency = 20
    headers: ClassVar[dict[str, str]] = {
        "User-Agent": "Cleture-Atlas/0.1 (+https://atlas.cleture.com)",
        "Accept": "text/html,application/xhtml+xml",
    }

    def __init__(
        self,
        *,
        repository: AtlasRepository,
        storage: ObjectStorage,
        fetcher: HttpAssetFetcher | None = None,
        parser: ConcitoParser | None = None,
        normalizer: ConcitoNormalizer | None = None,
    ) -> None:
        super().__init__(repository=repository, storage=storage)
        self.fetcher = fetcher or HttpAssetFetcher()
        self.parser = parser or ConcitoParser()
        self.normalizer = normalizer or ConcitoNormalizer()
        self._asset: FetchedAsset | None = None
        self._rows: tuple[ConcitoRow, ...] = ()
        self._revision: str | None = None

    async def check(self, context: PipelineContext) -> ChangeCheckResult:
        endpoint = str(context.source.history.snapshot_endpoints["database"])
        index = await self.fetcher.fetch(endpoint)
        try:
            if index.local_path is None:
                raise ValueError("CONCITO change detection requires a local HTML path")
            index_content = index.local_path.read_bytes()
        finally:
            if index.local_path is not None:
                index.local_path.unlink(missing_ok=True)
        self._revision = hashlib.sha256(index_content).hexdigest()
        dataset_version = context.source.history.snapshot_parameters["dataset_version"]
        context.source_dataset_version = dataset_version
        context.source_published_at = datetime(2024, 9, 23, tzinfo=UTC)
        previous = await self.repository.last_source_revision(
            context.source.code,
            parser_version=context.effective_parser_version,
            mapping_version=context.source.adapter.mapping_version,
        )
        changed = previous != self._revision
        if changed:
            self._asset = await self._build_bundle(endpoint, index_content, dataset_version)
        result = ChangeCheckResult(
            changed=changed,
            revision=self._revision if changed else None,
            reason=(
                f"The Big Climate Database {dataset_version} index changed"
                if changed
                else f"The Big Climate Database {dataset_version} index unchanged"
            ),
        )
        await self.repository.record_source_check(context.source.code, context.run.id, result)
        return result

    async def fetch(self, context: PipelineContext) -> FetchedAsset:
        del context
        if self._asset is None:
            raise ValueError("check must build the CONCITO acquisition bundle")
        return self._asset

    async def parse(self, context: PipelineContext) -> tuple[ParsedRecord, ...]:
        if context.fetched_asset is None or context.fetched_asset.local_path is None:
            raise ValueError("CONCITO parser requires the local acquisition bundle")
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
            raise ValueError("CONCITO raw bundle is unavailable")
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
        negative = context.metrics.get("negative_lca_results", 0)
        if not negative:
            return report
        return QualityReport(
            checked_records=report.checked_records,
            findings=(
                *report.findings,
                QualityFinding(
                    rule_code="concito.negative_lca_results",
                    severity=QualitySeverity.REVIEW_REQUIRED,
                    message=f"CONCITO reported negative lifecycle-stage results: {negative}",
                    details={"count": negative},
                ),
            ),
        )

    async def version(self, context: PipelineContext) -> str:
        try:
            return await super().version(context)
        finally:
            self._remove_bundle()

    async def close(self) -> None:
        self._remove_bundle()
        await self.fetcher.close()

    async def _build_bundle(
        self, endpoint: str, index_content: bytes, dataset_version: str
    ) -> FetchedAsset:
        soup = BeautifulSoup(index_content, "html.parser")
        activity_ids = [
            str(cell.get_text(" ", strip=True)) for cell in soup.select("tbody tr td:last-child")
        ]
        if len(activity_ids) != 2700 or len(set(activity_ids)) != 2700:
            raise RetryableIngestionError(
                f"CONCITO index expected 2,700 unique activities; found {len(activity_ids):,}"
            )
        semaphore = asyncio.Semaphore(self.detail_concurrency)
        timeout = httpx.Timeout(90.0, connect=20.0)
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=timeout, headers=self.headers
        ) as client:
            tasks = [
                self._download_detail(client, semaphore, endpoint, activity_id)
                for activity_id in activity_ids
            ]
            details = await asyncio.gather(*tasks)
        temporary = tempfile.NamedTemporaryFile(
            prefix="atlas-concito-", suffix=".zip", delete=False
        )
        temporary.close()
        path = Path(temporary.name)
        manifest = json.dumps(
            {
                "source": "CONCITO",
                "dataset_version": dataset_version,
                "index_sha256": hashlib.sha256(index_content).hexdigest(),
                "activities": len(activity_ids),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            self._write_deterministic(bundle, "bundle-manifest.json", manifest)
            self._write_deterministic(bundle, "index.html", index_content)
            for activity_id, content in zip(activity_ids, details, strict=True):
                self._write_deterministic(
                    bundle, f"activities/{activity_id}.html", content
                )
        return FetchedAsset(
            filename=f"the-big-climate-database-{dataset_version}.zip",
            local_path=path,
            source_url=endpoint,
            mime_type="application/zip",
            metadata={
                "acquisition_bundle": True,
                "dataset_version": dataset_version,
                "activities": len(activity_ids),
                "index_sha256": hashlib.sha256(index_content).hexdigest(),
            },
        )

    @staticmethod
    async def _download_detail(
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        endpoint: str,
        activity_id: str,
    ) -> bytes:
        url = f"{endpoint.rstrip('/')}/activity/{activity_id}/"
        async with semaphore:
            for attempt in range(4):
                try:
                    response = await client.get(url)
                    if response.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            "server error", request=response.request, response=response
                        )
                    response.raise_for_status()
                    return response.content
                except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError):
                    if attempt == 3:
                        break
                    await asyncio.sleep(2**attempt)
        raise RetryableIngestionError(f"CONCITO detail download failed: {activity_id}")

    def _version_key(self, context: PipelineContext) -> str:
        if context.raw_asset is None:
            raise ValueError("CONCITO raw metadata is unavailable")
        version = context.source.history.snapshot_parameters["dataset_version"]
        return f"{version}-{context.raw_asset.sha256[:12]}"

    def _remove_bundle(self) -> None:
        if self._asset is not None and self._asset.local_path is not None:
            self._asset.local_path.unlink(missing_ok=True)

    @staticmethod
    def _write_deterministic(bundle: zipfile.ZipFile, filename: str, content: bytes) -> None:
        info = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        bundle.writestr(info, content)

    @staticmethod
    def _rows_to_parquet(rows: tuple[ConcitoRow, ...]) -> bytes:
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
