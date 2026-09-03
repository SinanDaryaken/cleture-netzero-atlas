from __future__ import annotations

import asyncio
import hashlib
import io
import json
import tempfile
import zipfile
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
from atlas.ingestion.errors import PermanentIngestionError
from atlas.ports.storage import ObjectStorage
from sources.plastics_europe.normalizer import PlasticsEuropeNormalizer
from sources.plastics_europe.parser import (
    PackageSpec,
    PlasticsEuropeParser,
    PlasticsEuropeRow,
)


class PlasticsEuropeAdapter(BaseAtlasSourceAdapter):
    def __init__(
        self,
        *,
        repository: AtlasRepository,
        storage: ObjectStorage,
        fetcher: HttpAssetFetcher | None = None,
        parser: PlasticsEuropeParser | None = None,
        normalizer: PlasticsEuropeNormalizer | None = None,
    ) -> None:
        super().__init__(repository=repository, storage=storage)
        self.fetcher = fetcher or HttpAssetFetcher()
        self.parser = parser or PlasticsEuropeParser()
        self.normalizer = normalizer or PlasticsEuropeNormalizer()
        self._asset: FetchedAsset | None = None
        self._rows: tuple[PlasticsEuropeRow, ...] = ()

    async def check(self, context: PipelineContext) -> ChangeCheckResult:
        endpoints = context.source.history.snapshot_endpoints
        landing = await self.fetcher.fetch(str(endpoints["landing_page"]))
        if landing.local_path is None:
            raise PermanentIngestionError("Plastics Europe landing page was not downloaded")
        landing_content = landing.local_path.read_bytes()
        package_urls = {
            spec.key: str(endpoints[spec.key]) for spec in self.parser.package_specs
        }
        for url in package_urls.values():
            if url.encode() not in landing_content:
                landing.local_path.unlink(missing_ok=True)
                raise PermanentIngestionError(
                    f"Plastics Europe landing page no longer links {url}"
                )
        results = await asyncio.gather(
            *(self.fetcher.fetch(url) for url in package_urls.values()),
            return_exceptions=True,
        )
        assets = [result for result in results if isinstance(result, FetchedAsset)]
        errors = [result for result in results if isinstance(result, Exception)]
        if errors:
            landing.local_path.unlink(missing_ok=True)
            for asset in assets:
                if asset.local_path is not None:
                    asset.local_path.unlink(missing_ok=True)
            raise errors[0]
        package_assets = dict(zip(package_urls, assets, strict=True))
        package_hashes: dict[str, str] = {}
        for key, asset in package_assets.items():
            if asset.local_path is None:
                raise PermanentIngestionError(
                    f"Plastics Europe package {key} was not downloaded"
                )
            package_hashes[key] = hashlib.sha256(asset.local_path.read_bytes()).hexdigest()
        signature = "\n".join(
            f"{key}:{package_hashes[key]}" for key in sorted(package_hashes)
        )
        revision = hashlib.sha256(signature.encode()).hexdigest()
        dataset_version = context.source.history.snapshot_parameters["dataset_version"]
        context.source_dataset_version = dataset_version
        context.source_published_at = datetime(2026, 3, 13, tzinfo=UTC)
        previous = await self.repository.last_source_revision(
            context.source.code,
            parser_version=context.effective_parser_version,
            mapping_version=context.source.adapter.mapping_version,
        )
        changed = previous != revision
        if changed:
            self._asset = self._build_bundle(
                landing_content,
                package_urls=package_urls,
                package_assets=package_assets,
                package_hashes=package_hashes,
                dataset_version=dataset_version,
            )
        landing.local_path.unlink(missing_ok=True)
        for asset in package_assets.values():
            if asset.local_path is not None:
                asset.local_path.unlink(missing_ok=True)
        result = ChangeCheckResult(
            changed=changed,
            revision=revision if changed else None,
            reason=(
                f"Plastics Europe Eco-profiles {dataset_version} packages changed"
                if changed
                else f"Plastics Europe Eco-profiles {dataset_version} packages unchanged"
            ),
        )
        await self.repository.record_source_check(context.source.code, context.run.id, result)
        return result

    async def fetch(self, context: PipelineContext) -> FetchedAsset:
        del context
        if self._asset is None:
            raise ValueError("check must build the Plastics Europe acquisition bundle")
        return self._asset

    async def parse(self, context: PipelineContext) -> tuple[ParsedRecord, ...]:
        if context.fetched_asset is None or context.fetched_asset.local_path is None:
            raise ValueError("Plastics Europe parser requires the local bundle")
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
            raise ValueError("Plastics Europe raw bundle is unavailable")
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

    async def version(self, context: PipelineContext) -> str:
        try:
            return await super().version(context)
        finally:
            self._remove_bundle()

    async def close(self) -> None:
        self._remove_bundle()
        await self.fetcher.close()

    def _build_bundle(
        self,
        landing_content: bytes,
        *,
        package_urls: dict[str, str],
        package_assets: dict[str, FetchedAsset],
        package_hashes: dict[str, str],
        dataset_version: str,
    ) -> FetchedAsset:
        temporary = tempfile.NamedTemporaryFile(
            prefix="atlas-plastics-europe-", suffix=".zip", delete=False
        )
        temporary.close()
        path = Path(temporary.name)
        metadata = {
            key: {
                "filename": self._spec(key).filename,
                "url": package_urls[key],
                "sha256": package_hashes[key],
            }
            for key in sorted(package_assets)
        }
        manifest = json.dumps(
            {
                "source": "Plastics Europe",
                "dataset_version": dataset_version,
                "packages": metadata,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            self._write_deterministic(bundle, "bundle-manifest.json", manifest)
            self._write_deterministic(bundle, "landing-page.html", landing_content)
            for key in sorted(package_assets):
                asset_path = package_assets[key].local_path
                if asset_path is None:
                    raise PermanentIngestionError(
                        f"Plastics Europe package {key} has no local path"
                    )
                self._write_deterministic(
                    bundle,
                    f"packages/{self._spec(key).filename}",
                    asset_path.read_bytes(),
                )
        return FetchedAsset(
            filename=f"plasticseurope-eco-profiles-{dataset_version}.zip",
            local_path=path,
            source_url=PlasticsEuropeNormalizer.official_url,
            mime_type="application/zip",
            metadata={
                "acquisition_bundle": True,
                "dataset_version": dataset_version,
                "packages": len(package_assets),
                "package_sha256": package_hashes,
            },
        )

    def _spec(self, key: str) -> PackageSpec:
        return next(spec for spec in self.parser.package_specs if spec.key == key)

    def _version_key(self, context: PipelineContext) -> str:
        if context.raw_asset is None:
            raise ValueError("Plastics Europe raw metadata is unavailable")
        version = context.source.history.snapshot_parameters["dataset_version"]
        return f"{version}-{context.raw_asset.sha256[:12]}"

    def _remove_bundle(self) -> None:
        if self._asset is not None and self._asset.local_path is not None:
            self._asset.local_path.unlink(missing_ok=True)

    @staticmethod
    def _write_deterministic(
        bundle: zipfile.ZipFile, filename: str, content: bytes
    ) -> None:
        info = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        bundle.writestr(info, content)

    @staticmethod
    def _rows_to_parquet(rows: tuple[PlasticsEuropeRow, ...]) -> bytes:
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
