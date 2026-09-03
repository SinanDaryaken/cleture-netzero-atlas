from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

from atlas.config import Settings
from atlas.domain.models import (
    FetchedAsset,
    ProcessingArtifactReference,
    RawAssetReference,
    SourceDefinition,
)
from atlas.ingestion.errors import PermanentIngestionError, RetryableIngestionError


class S3ObjectStorage:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client or boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name="us-east-1",
        )

    async def ensure_buckets(self) -> None:
        for bucket in (self._settings.s3_raw_bucket, self._settings.s3_processing_bucket):
            await asyncio.to_thread(self._ensure_bucket, bucket)

    async def store_raw(self, source: SourceDefinition, asset: FetchedAsset) -> RawAssetReference:
        sha256, size = await asyncio.to_thread(self._hash_asset, asset)
        stamp = asset.downloaded_at.astimezone(UTC).strftime("%Y/%m/%d")
        safe_filename = Path(asset.filename).name
        key = f"sources/{source.code.lower()}/{stamp}/{sha256}/{safe_filename}"
        await asyncio.to_thread(
            self._put_immutable,
            self._settings.s3_raw_bucket,
            key,
            asset,
            sha256,
            asset.mime_type or "application/octet-stream",
        )
        return RawAssetReference(
            bucket=self._settings.s3_raw_bucket,
            object_key=key,
            sha256=sha256,
            filename=safe_filename,
            source_url=asset.source_url,
            mime_type=asset.mime_type,
            size_bytes=size,
            downloaded_at=asset.downloaded_at,
            metadata=asset.metadata,
        )

    async def store_processing(
        self,
        *,
        source_code: str,
        version_key: str,
        layer: str,
        content: bytes,
        row_count: int,
        extension: str,
    ) -> ProcessingArtifactReference:
        sha256 = hashlib.sha256(content).hexdigest()
        key = (
            f"sources/{source_code.lower()}/{version_key}/{layer}/{sha256}.{extension.lstrip('.')}"
        )
        await asyncio.to_thread(
            self._put_bytes_immutable,
            self._settings.s3_processing_bucket,
            key,
            content,
            sha256,
            "application/vnd.apache.parquet"
            if extension == "parquet"
            else "application/octet-stream",
        )
        return ProcessingArtifactReference(
            layer=layer,
            bucket=self._settings.s3_processing_bucket,
            object_key=key,
            sha256=sha256,
            row_count=row_count,
        )

    def _ensure_bucket(self, bucket: str) -> None:
        try:
            self._client.head_bucket(Bucket=bucket)
        except ClientError as error:
            status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status not in {403, 404}:
                raise RetryableIngestionError(f"cannot inspect bucket {bucket}") from error
            self._client.create_bucket(Bucket=bucket)
        self._client.put_bucket_versioning(
            Bucket=bucket,
            VersioningConfiguration={"Status": "Enabled"},
        )

    @staticmethod
    def _hash_asset(asset: FetchedAsset) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        if asset.content is not None:
            digest.update(asset.content)
            return digest.hexdigest(), len(asset.content)
        if asset.local_path is None:
            raise PermanentIngestionError("asset has no content")
        with asset.local_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        return digest.hexdigest(), size

    def _put_immutable(
        self,
        bucket: str,
        key: str,
        asset: FetchedAsset,
        sha256: str,
        content_type: str,
    ) -> None:
        if self._object_exists(bucket, key, sha256):
            return
        body: Any
        handle = None
        try:
            if asset.content is not None:
                body = asset.content
            elif asset.local_path is not None:
                handle = asset.local_path.open("rb")
                body = handle
            else:
                raise PermanentIngestionError("asset has no content")
            self._client.put_object(
                Bucket=bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
                Metadata={"sha256": sha256, "immutable": "true"},
            )
        except ClientError as error:
            raise RetryableIngestionError(f"cannot store raw object {key}") from error
        finally:
            if handle is not None:
                handle.close()

    def _put_bytes_immutable(
        self,
        bucket: str,
        key: str,
        content: bytes,
        sha256: str,
        content_type: str,
    ) -> None:
        if self._object_exists(bucket, key, sha256):
            return
        try:
            self._client.put_object(
                Bucket=bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
                Metadata={"sha256": sha256, "immutable": "true"},
            )
        except ClientError as error:
            raise RetryableIngestionError(f"cannot store processing object {key}") from error

    def _object_exists(self, bucket: str, key: str, sha256: str) -> bool:
        try:
            response = self._client.head_object(Bucket=bucket, Key=key)
        except ClientError as error:
            status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status == 404:
                return False
            raise RetryableIngestionError(f"cannot inspect object {key}") from error
        existing = response.get("Metadata", {}).get("sha256")
        if existing != sha256:
            raise PermanentIngestionError(f"immutable object checksum mismatch: {key}")
        return True
