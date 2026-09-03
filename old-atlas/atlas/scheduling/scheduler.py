from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from croniter import croniter

from atlas.infrastructure.database.repositories import AtlasRepository
from atlas.ingestion.registry import SourceRegistry


class AtlasScheduler:
    def __init__(
        self,
        repository: AtlasRepository,
        registry: SourceRegistry,
        *,
        poll_seconds: int = 30,
        ingestion_enabled: bool = False,
    ) -> None:
        self.repository = repository
        self.registry = registry
        self.poll_seconds = poll_seconds
        self.ingestion_enabled = ingestion_enabled

    async def tick(self, now: datetime | None = None) -> int:
        if not self.ingestion_enabled:
            return 0
        current = now or datetime.now(UTC)
        source_codes = await self.repository.due_source_codes(current)
        created = 0
        for source_code in source_codes:
            result = await self.repository.request_run(source_code, "scheduler")
            if result.created:
                created += 1
            schedule = self.registry.get(source_code).ingestion.schedule
            next_check = croniter(schedule, current).get_next(datetime)
            if next_check.tzinfo is None:
                next_check = next_check.replace(tzinfo=UTC)
            await self.repository.set_next_check(source_code, next_check)
        return created

    async def run_forever(self) -> None:
        while True:
            await self.tick()
            await asyncio.sleep(self.poll_seconds)
