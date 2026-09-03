from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
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
from atlas.ingestion.base import BaseAtlasSourceAdapter
from atlas.ingestion.errors import PermanentIngestionError, RetryableIngestionError
from atlas.ports.storage import ObjectStorage
from sources.eea.normalizer import EeaNormalizer
from sources.eea.parser import EeaDocument, EeaParser


@dataclass(frozen=True)
class EeaSnapshot:
    asset: FetchedAsset
    revision: str
    row_count: int
    index_name: str
    refreshed_at: str


class EeaApiClient:
    PAGE_SIZE = 5_000

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(180.0, connect=30.0),
            headers={"User-Agent": "Cleture-Atlas/0.1 (+https://atlas.cleture.com)"},
        )

    async def fetch_snapshot(self, endpoint: str, *, edition: int) -> EeaSnapshot:
        records: list[dict[str, Any]] = []
        index_name: str | None = None
        expected_total: int | None = None
        search_after: list[Any] | None = None
        while True:
            query: dict[str, Any] = {
                "size": self.PAGE_SIZE,
                "track_total_hits": True,
                "sort": [{"ID": "asc"}],
                "query": {"match_all": {}},
            }
            if search_after is not None:
                query["search_after"] = search_after
            payload = await self._post(endpoint, query)
            hits_container = payload.get("hits")
            if not isinstance(hits_container, dict) or not isinstance(
                hits_container.get("hits"), list
            ):
                raise PermanentIngestionError("EEA viewer API response contract changed")
            total = hits_container.get("total")
            if not isinstance(total, dict) or total.get("relation") != "eq":
                raise PermanentIngestionError("EEA viewer API did not return an exact total")
            current_total = total.get("value")
            if not isinstance(current_total, int):
                raise PermanentIngestionError("EEA viewer API total is invalid")
            if expected_total is None:
                expected_total = current_total
            elif current_total != expected_total:
                raise RetryableIngestionError("EEA viewer changed during snapshot pagination")

            hits = hits_container["hits"]
            if not hits:
                break
            for hit in hits:
                if not isinstance(hit, dict) or not isinstance(hit.get("_source"), dict):
                    raise PermanentIngestionError("EEA viewer API hit contract changed")
                current_index = hit.get("_index")
                if not isinstance(current_index, str):
                    raise PermanentIngestionError("EEA viewer API index identity is missing")
                if index_name is None:
                    index_name = current_index
                elif current_index != index_name:
                    raise RetryableIngestionError("EEA viewer index changed during pagination")
                records.append(hit["_source"])
            last_sort = hits[-1].get("sort")
            if not isinstance(last_sort, list) or not last_sort:
                raise PermanentIngestionError("EEA viewer API pagination token is missing")
            search_after = last_sort
            if expected_total is not None and len(records) >= expected_total:
                break

        if expected_total is None or index_name is None or len(records) != expected_total:
            raise RetryableIngestionError(
                f"EEA viewer snapshot was incomplete ({len(records)}/{expected_total})"
            )
        ids: list[int] = []
        for record in records:
            record_id = record.get("ID")
            if not isinstance(record_id, int):
                raise PermanentIngestionError("EEA viewer record ID is invalid")
            ids.append(record_id)
        if ids != sorted(ids) or len(set(ids)) != len(ids):
            raise PermanentIngestionError("EEA viewer record IDs are not unique and ordered")

        stable_records = json.dumps(
            records,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        revision = hashlib.sha256(stable_records).hexdigest()
        refreshed_at = self._refreshed_at(index_name)
        content = json.dumps(
            {
                "edition": edition,
                "index_name": index_name,
                "refreshed_at": refreshed_at,
                "records": records,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return EeaSnapshot(
            asset=FetchedAsset(
                filename=f"emep-eea-guidebook-{edition}-{refreshed_at[:10]}-{revision[:12]}.json",
                content=content,
                source_url=endpoint,
                mime_type="application/json",
                metadata={
                    "viewer_index": index_name,
                    "viewer_refreshed_at": refreshed_at,
                    "row_count": expected_total,
                },
            ),
            revision=revision,
            row_count=expected_total,
            index_name=index_name,
            refreshed_at=refreshed_at,
        )

    async def _post(self, endpoint: str, query: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.post(
                endpoint,
                json={
                    "source": json.dumps(
                        query,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                },
            )
            if response.status_code >= 500:
                raise RetryableIngestionError(f"EEA viewer API returned {response.status_code}")
            response.raise_for_status()
            payload = response.json()
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise RetryableIngestionError("EEA viewer API request failed") from error
        except httpx.HTTPStatusError as error:
            raise PermanentIngestionError(
                f"EEA viewer API rejected the request with {error.response.status_code}"
            ) from error
        except ValueError as error:
            raise PermanentIngestionError("EEA viewer API response is not valid JSON") from error
        if not isinstance(payload, dict):
            raise PermanentIngestionError("EEA viewer API response is not an object")
        return payload

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @staticmethod
    def _refreshed_at(index_name: str) -> str:
        match = re.fullmatch(r"efdb_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})_(\d{2})", index_name)
        if match is None:
            raise PermanentIngestionError("EEA viewer index name contract changed")
        return f"{match.group(1)}T{match.group(2)}:{match.group(3)}:{match.group(4)}Z"


class EeaAdapter(BaseAtlasSourceAdapter):
    EDITION = 2023

    def __init__(
        self,
        *,
        repository: AtlasRepository,
        storage: ObjectStorage,
        api_client: EeaApiClient | None = None,
        parser: EeaParser | None = None,
        normalizer: EeaNormalizer | None = None,
    ) -> None:
        super().__init__(repository=repository, storage=storage)
        self.api_client = api_client or EeaApiClient()
        self.parser = parser or EeaParser()
        self.normalizer = normalizer or EeaNormalizer()
        self._snapshot: EeaSnapshot | None = None
        self._document: EeaDocument | None = None

    async def check(self, context: PipelineContext) -> ChangeCheckResult:
        endpoint = context.source.history.snapshot_endpoints["emission_factor_viewer"]
        self._snapshot = await self.api_client.fetch_snapshot(
            str(endpoint),
            edition=self.EDITION,
        )
        context.source_dataset_version = (
            f"guidebook-{self.EDITION}-viewer-{self._snapshot.refreshed_at[:10]}"
        )
        context.source_published_at = datetime(2023, 10, 2, tzinfo=UTC)
        context.metrics.update(
            {
                "reported_rows": self._snapshot.row_count,
                "release_year": self.EDITION,
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
                f"EEA viewer changed ({self._snapshot.row_count} records)"
                if changed
                else f"EEA viewer unchanged ({self._snapshot.row_count} records)"
            ),
        )
        await self.repository.record_source_check(context.source.code, context.run.id, result)
        return result

    async def fetch(self, context: PipelineContext) -> FetchedAsset:
        del context
        if self._snapshot is None:
            raise ValueError("check must fetch the EEA snapshot before fetch")
        return self._snapshot.asset

    async def parse(self, context: PipelineContext) -> tuple[ParsedRecord, ...]:
        if context.fetched_asset is None or context.fetched_asset.content is None:
            raise ValueError("EEA parser requires the fetched JSON snapshot")
        self._document = self.parser.parse(context.fetched_asset.content)
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
        if context.raw_asset is None or self._snapshot is None or self._document is None:
            raise ValueError("EEA snapshot metadata is unavailable")
        factors, observations, metrics = self.normalizer.normalize(
            self._document.rows,
            raw=context.raw_asset,
            dataset_revision=self._snapshot.revision,
            dataset_version=context.source_dataset_version or f"guidebook-{self.EDITION}",
            index_name=self._snapshot.index_name,
            refreshed_at=self._snapshot.refreshed_at,
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
        excluded = context.metrics.get("excluded_non_numeric_rows", 0)
        if excluded:
            findings.append(
                QualityFinding(
                    rule_code="eea.non_numeric_source_values",
                    severity=QualitySeverity.WARNING,
                    message=f"EEA rows without one numeric value remain raw/parsed: {excluded}",
                    details={"count": excluded},
                )
            )
        return QualityReport(checked_records=report.checked_records, findings=tuple(findings))

    async def close(self) -> None:
        await self.api_client.close()

    def _version_key(self, context: PipelineContext) -> str:
        if context.raw_asset is None or self._snapshot is None:
            raise ValueError("EEA raw metadata is unavailable")
        return f"{self._snapshot.refreshed_at[:10]}-{context.raw_asset.sha256[:12]}"

    @staticmethod
    def _records_to_parquet(records: tuple[ParsedRecord, ...]) -> bytes:
        payloads = [
            {
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
