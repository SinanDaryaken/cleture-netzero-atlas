from typing import Protocol

from atlas.domain.models import (
    FetchedAsset,
    ProcessingArtifactReference,
    RawAssetReference,
    SourceDefinition,
)


class ObjectStorage(Protocol):
    async def ensure_buckets(self) -> None: ...

    async def store_raw(
        self, source: SourceDefinition, asset: FetchedAsset
    ) -> RawAssetReference: ...

    async def store_processing(
        self,
        *,
        source_code: str,
        version_key: str,
        layer: str,
        content: bytes,
        row_count: int,
        extension: str,
    ) -> ProcessingArtifactReference: ...
