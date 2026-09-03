from typing import Protocol

from atlas.domain.models import (
    CanonicalFactor,
    ChangeCheckResult,
    ComparisonReport,
    FetchedAsset,
    ParsedRecord,
    PipelineContext,
    QualityReport,
    RawAssetReference,
)


class AtlasSourceAdapter(Protocol):
    """Source-specific behavior consumed by the source-agnostic orchestrator."""

    async def check(self, context: PipelineContext) -> ChangeCheckResult: ...

    async def fetch(self, context: PipelineContext) -> FetchedAsset: ...

    async def store_raw(self, context: PipelineContext) -> RawAssetReference: ...

    async def parse(self, context: PipelineContext) -> tuple[ParsedRecord, ...]: ...

    async def normalize(self, context: PipelineContext) -> tuple[CanonicalFactor, ...]: ...

    async def validate(self, context: PipelineContext) -> QualityReport: ...

    async def compare(self, context: PipelineContext) -> ComparisonReport: ...

    async def version(self, context: PipelineContext) -> str: ...

    async def publish(self, context: PipelineContext) -> None: ...

    async def close(self) -> None: ...
