from __future__ import annotations

import hashlib
import io
import json
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

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
from atlas.infrastructure.http import HttpAssetFetcher
from atlas.ingestion.base import BaseAtlasSourceAdapter
from atlas.ports.storage import ObjectStorage
from sources.unfccc_tuik.normalizer import UnfcccTuikNormalizer
from sources.unfccc_tuik.parser import UnfcccTuikParser, UnfcccTuikRow


class UnfcccTuikAdapter(BaseAtlasSourceAdapter):
    def __init__(
        self,
        *,
        repository: AtlasRepository,
        storage: ObjectStorage,
        fetcher: HttpAssetFetcher | None = None,
        parser: UnfcccTuikParser | None = None,
        normalizer: UnfcccTuikNormalizer | None = None,
        local_asset_root: Path | None = None,
    ) -> None:
        super().__init__(repository=repository, storage=storage)
        self.fetcher = fetcher or HttpAssetFetcher()
        self.parser = parser or UnfcccTuikParser()
        self.normalizer = normalizer or UnfcccTuikNormalizer(
            Path(__file__).with_name("mappings.yaml")
        )
        self.local_asset_root = local_asset_root or get_settings().local_source_asset_root
        self._asset_url: str | None = None
        self._local_asset: Path | None = None
        self._submission_year: int | None = None
        self._submission_status: str | None = None
        self._schema_family: str | None = None
        self._revision: str | None = None
        self._rows: tuple[UnfcccTuikRow, ...] = ()

    async def check(self, context: PipelineContext) -> ChangeCheckResult:
        submission_year = (
            context.run.requested_reference_year
            if context.run.requested_reference_year is not None
            else context.source.history.end_year
        )
        if submission_year is None:
            raise ValueError("UNFCCC submission year is unavailable")
        schema = context.source.history.schema_for(submission_year)
        self._submission_year = submission_year
        self._submission_status = context.source.history.snapshot_parameters[
            f"status_{submission_year}"
        ]
        self._schema_family = schema.name
        self._asset_url = str(context.source.history.release_pages[submission_year])
        context.source_dataset_version = f"{submission_year}:{self._submission_status}"
        context.parser_version = schema.parser_version
        context.metrics.update(
            {
                "release_year": submission_year,
                "submission_year": submission_year,
            }
        )
        filename = context.source.history.snapshot_parameters[f"asset_{submission_year}"]
        candidate = (
            self.local_asset_root / "unfccc-tuik" / filename
            if self.local_asset_root is not None
            else None
        )
        if candidate is not None and candidate.is_file():
            self._local_asset = candidate
            self._revision = self._sha256(candidate)
            previous = await self.repository.last_source_revision(
                context.source.code,
                reference_year=submission_year,
                parser_version=context.effective_parser_version,
                mapping_version=context.source.adapter.mapping_version,
            )
            result = ChangeCheckResult(
                changed=previous != self._revision,
                revision=self._revision if previous != self._revision else None,
                reason=(
                    f"UNFCCC/TÜİK submission {submission_year} local structured archive changed"
                    if previous != self._revision
                    else f"UNFCCC/TÜİK submission {submission_year} archive unchanged"
                ),
            )
        else:
            previous = await self.repository.last_source_revision(
                context.source.code,
                reference_year=submission_year,
                parser_version=context.effective_parser_version,
                mapping_version=context.source.adapter.mapping_version,
            )
            result = await self.fetcher.check(self._asset_url, previous)
            self._revision = result.revision
        await self.repository.record_source_check(context.source.code, context.run.id, result)
        return result

    async def fetch(self, context: PipelineContext) -> FetchedAsset:
        if self._asset_url is None or self._submission_year is None:
            raise ValueError("check must resolve the UNFCCC submission before fetch")
        if self._local_asset is not None:
            temporary = tempfile.NamedTemporaryFile(
                prefix=f"atlas-unfccc-tuik-{self._submission_year}-",
                suffix=".zip",
                delete=False,
            )
            temporary.close()
            path = Path(temporary.name)
            shutil.copyfile(self._local_asset, path)
            asset = FetchedAsset(
                filename=self._local_asset.name,
                local_path=path,
                source_url=self._asset_url,
                mime_type="application/zip",
                downloaded_at=datetime.now(UTC),
            )
        else:
            asset = await self.fetcher.fetch(self._asset_url)
        if asset.local_path is None:
            raise ValueError("UNFCCC submission fetch requires a local ZIP path")
        metadata = {
            "submission_year": self._submission_year,
            "submission_status": self._submission_status,
            "schema_family": self._schema_family,
            "members": self._member_metadata(asset.local_path),
        }
        return asset.model_copy(update={"metadata": metadata})

    async def parse(self, context: PipelineContext) -> tuple[ParsedRecord, ...]:
        if context.fetched_asset is None or context.fetched_asset.local_path is None:
            raise ValueError("UNFCCC/TÜİK parser requires a local ZIP path")
        if (
            self._submission_year is None
            or self._submission_status is None
            or self._schema_family is None
        ):
            raise ValueError("UNFCCC/TÜİK submission metadata is unavailable")
        self._rows = self.parser.parse(
            context.fetched_asset.local_path,
            submission_year=self._submission_year,
            submission_status=self._submission_status,
            schema_family=self._schema_family,
        )
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
        if context.raw_asset is None or self._revision is None:
            raise ValueError("UNFCCC/TÜİK raw submission is unavailable")
        observations, factors, metrics = self.normalizer.normalize(
            self._rows,
            raw=context.raw_asset,
            dataset_revision=self._revision,
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
        if self._submission_status != "submitted":
            findings.append(
                QualityFinding(
                    rule_code="unfccc.submission_status_not_final",
                    severity=QualitySeverity.REVIEW_REQUIRED,
                    message=(
                        f"UNFCCC submission {self._submission_year} source status is "
                        f"{self._submission_status}"
                    ),
                    details={
                        "submission_year": self._submission_year,
                        "submission_status": self._submission_status,
                    },
                )
            )
        return QualityReport(checked_records=report.checked_records, findings=tuple(findings))

    async def version(self, context: PipelineContext) -> str:
        try:
            return await super().version(context)
        finally:
            self._remove_temporary(context)

    async def close(self) -> None:
        await self.fetcher.close()

    def _version_key(self, context: PipelineContext) -> str:
        if self._submission_year is None or self._revision is None:
            raise ValueError("UNFCCC/TÜİK version metadata is unavailable")
        return f"{self._submission_year}-{self._revision[:12]}"

    @staticmethod
    def _member_metadata(path: Path) -> list[dict[str, object]]:
        members: list[dict[str, object]] = []
        with zipfile.ZipFile(path) as archive:
            for info in sorted(archive.infolist(), key=lambda item: item.filename):
                if not info.filename.lower().endswith(".xlsx"):
                    continue
                content = archive.read(info.filename)
                members.append(
                    {
                        "filename": info.filename,
                        "size_bytes": info.file_size,
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                )
        return members

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _remove_temporary(context: PipelineContext) -> None:
        if context.fetched_asset is not None and context.fetched_asset.local_path is not None:
            context.fetched_asset.local_path.unlink(missing_ok=True)

    @staticmethod
    def _rows_to_parquet(rows: tuple[UnfcccTuikRow, ...]) -> bytes:
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
