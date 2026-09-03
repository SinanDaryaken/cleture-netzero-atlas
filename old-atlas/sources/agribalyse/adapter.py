from __future__ import annotations

import hashlib
import io
import json
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

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
from sources.agribalyse.normalizer import AgribalyseNormalizer
from sources.agribalyse.parser import AgribalyseParser, AgribalyseRow


class AgribalyseAdapter(BaseAtlasSourceAdapter):
    member_filenames: ClassVar[dict[str, str]] = {
        "conventional": "agribalyse-3.2-conventional.xlsx",
        "organic": "agribalyse-3.2-organic.xlsx",
        "food": "agribalyse-3.2-food.xlsx",
    }

    def __init__(
        self,
        *,
        repository: AtlasRepository,
        storage: ObjectStorage,
        fetcher: HttpAssetFetcher | None = None,
        parser: AgribalyseParser | None = None,
        normalizer: AgribalyseNormalizer | None = None,
    ) -> None:
        super().__init__(repository=repository, storage=storage)
        self.fetcher = fetcher or HttpAssetFetcher()
        self.parser = parser or AgribalyseParser()
        self.normalizer = normalizer or AgribalyseNormalizer()
        self._bundle: FetchedAsset | None = None
        self._rows: tuple[AgribalyseRow, ...] = ()
        self._revision: str | None = None

    async def check(self, context: PipelineContext) -> ChangeCheckResult:
        dataset_version = context.source.history.snapshot_parameters["dataset_version"]
        self._bundle, self._revision = await self._build_bundle(context, dataset_version)
        context.source_dataset_version = dataset_version
        context.metrics.update(
            {
                "bundle_members": len(self.member_filenames),
            }
        )
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
                f"AGRIBALYSE {dataset_version} public result bundle changed"
                if changed
                else f"AGRIBALYSE {dataset_version} public result bundle unchanged"
            ),
        )
        await self.repository.record_source_check(context.source.code, context.run.id, result)
        return result

    async def fetch(self, context: PipelineContext) -> FetchedAsset:
        del context
        if self._bundle is None:
            raise ValueError("check must build the AGRIBALYSE acquisition bundle")
        return self._bundle

    async def parse(self, context: PipelineContext) -> tuple[ParsedRecord, ...]:
        if context.fetched_asset is None or context.fetched_asset.local_path is None:
            raise ValueError("AGRIBALYSE parser requires the local acquisition bundle")
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
            raise ValueError("AGRIBALYSE raw acquisition bundle is unavailable")
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
        findings = list(report.findings)
        negative = context.metrics.get("negative_lca_results", 0)
        if negative:
            findings.append(
                QualityFinding(
                    rule_code="agribalyse.negative_lca_results",
                    severity=QualitySeverity.REVIEW_REQUIRED,
                    message=f"AGRIBALYSE reported negative climate LCA results: {negative}",
                    details={"count": negative},
                )
            )
        return QualityReport(checked_records=report.checked_records, findings=tuple(findings))

    async def version(self, context: PipelineContext) -> str:
        try:
            return await super().version(context)
        finally:
            self._remove_bundle()

    async def close(self) -> None:
        self._remove_bundle()
        await self.fetcher.close()

    async def _build_bundle(
        self, context: PipelineContext, dataset_version: str
    ) -> tuple[FetchedAsset, str]:
        assets: list[dict[str, object]] = []
        contents: dict[str, bytes] = {}
        downloaded_at = datetime.now(UTC)
        for role in ("conventional", "organic", "food"):
            source_url = str(context.source.history.snapshot_endpoints[role])
            fetched = await self.fetcher.fetch(source_url)
            try:
                if fetched.local_path is None:
                    raise ValueError("AGRIBALYSE member download requires a local path")
                content = fetched.local_path.read_bytes()
            finally:
                if fetched.local_path is not None:
                    fetched.local_path.unlink(missing_ok=True)
            filename = self.member_filenames[role]
            checksum = hashlib.sha256(content).hexdigest()
            contents[filename] = content
            assets.append(
                {
                    "role": role,
                    "filename": filename,
                    "source_url": source_url,
                    "sha256": checksum,
                    "size_bytes": len(content),
                }
            )
        manifest = {
            "source": context.source.code,
            "dataset_version": dataset_version,
            "assets": assets,
        }
        stable_manifest = json.dumps(
            manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        revision = hashlib.sha256(stable_manifest).hexdigest()
        temporary = tempfile.NamedTemporaryFile(
            prefix="atlas-agribalyse-", suffix=".zip", delete=False
        )
        temporary.close()
        path = Path(temporary.name)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            self._write_deterministic(bundle, "bundle-manifest.json", stable_manifest)
            for filename in sorted(contents):
                self._write_deterministic(bundle, filename, contents[filename])
        return (
            FetchedAsset(
                filename=f"agribalyse-{dataset_version}-{revision[:12]}.zip",
                local_path=path,
                source_url=context.source.location.landing_page,
                mime_type="application/zip",
                downloaded_at=downloaded_at,
                metadata={
                    "acquisition_bundle": True,
                    "dataset_version": dataset_version,
                    "assets": assets,
                },
            ),
            revision,
        )

    @staticmethod
    def _write_deterministic(bundle: zipfile.ZipFile, filename: str, content: bytes) -> None:
        info = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        bundle.writestr(info, content)

    def _version_key(self, context: PipelineContext) -> str:
        if context.raw_asset is None or self._revision is None:
            raise ValueError("AGRIBALYSE bundle metadata is unavailable")
        version = context.source.history.snapshot_parameters["dataset_version"]
        return f"{version}-{self._revision[:12]}"

    def _remove_bundle(self) -> None:
        if self._bundle is not None and self._bundle.local_path is not None:
            self._bundle.local_path.unlink(missing_ok=True)

    @staticmethod
    def _rows_to_parquet(rows: tuple[AgribalyseRow, ...]) -> bytes:
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
