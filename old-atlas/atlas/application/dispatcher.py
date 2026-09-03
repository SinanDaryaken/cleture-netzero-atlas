from __future__ import annotations

import asyncio

from atlas.infrastructure.database.repositories import AtlasRepository
from atlas.infrastructure.queue import RedisStreamQueue


class OutboxDispatcher:
    def __init__(self, repository: AtlasRepository, queue: RedisStreamQueue) -> None:
        self.repository = repository
        self.queue = queue

    async def dispatch_once(self) -> int:
        events = await self.repository.claim_outbox()
        published = 0
        for event in events:
            try:
                await self.queue.publish(
                    event_id=str(event.id),
                    event_type=event.event_type,
                    payload=event.payload,
                )
            except Exception as error:
                await self.repository.mark_outbox_failed(event.id, str(error))
                continue
            await self.repository.mark_outbox_published(event.id)
            published += 1
        return published

    async def run_forever(self, poll_seconds: float = 1.0) -> None:
        await self.queue.ensure_group()
        while True:
            count = await self.dispatch_once()
            if count == 0:
                await asyncio.sleep(poll_seconds)
