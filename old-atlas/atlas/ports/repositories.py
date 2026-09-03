from typing import Protocol

from atlas.domain.models import PipelineRun


class RunRepository(Protocol):
    async def save(self, run: PipelineRun) -> None: ...


class NullRunRepository:
    async def save(self, run: PipelineRun) -> None:
        del run
