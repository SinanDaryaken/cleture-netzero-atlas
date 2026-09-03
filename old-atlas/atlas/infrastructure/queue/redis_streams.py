from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from atlas.config import Settings


@dataclass(frozen=True)
class StreamJob:
    message_id: str
    event_id: str
    event_type: str
    payload: dict[str, Any]


class RedisStreamQueue:
    def __init__(self, settings: Settings, client: Redis | None = None) -> None:
        self.stream = settings.redis_stream
        self.group = settings.redis_consumer_group
        self.client = client or Redis.from_url(settings.redis_url, decode_responses=True)

    async def ensure_group(self) -> None:
        try:
            await self.client.xgroup_create(self.stream, self.group, id="0-0", mkstream=True)
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def publish(self, *, event_id: str, event_type: str, payload: dict[str, Any]) -> str:
        return str(
            await self.client.xadd(
                self.stream,
                {
                    "event_id": event_id,
                    "event_type": event_type,
                    "payload": json.dumps(payload, separators=(",", ":"), sort_keys=True),
                },
            )
        )

    async def read(self, consumer: str, block_ms: int = 5000) -> tuple[StreamJob, ...]:
        response = await self.client.xreadgroup(
            self.group,
            consumer,
            {self.stream: ">"},
            count=1,
            block=block_ms,
        )
        return self._decode(response)

    async def reclaim_stale(
        self, consumer: str, min_idle_ms: int = 60_000
    ) -> tuple[StreamJob, ...]:
        response = await self.client.xautoclaim(
            self.stream,
            self.group,
            consumer,
            min_idle_ms,
            start_id="0-0",
            count=10,
        )
        messages = response[1] if len(response) > 1 else []
        return tuple(self._job(message_id, fields) for message_id, fields in messages)

    async def acknowledge(self, message_id: str) -> None:
        await self.client.xack(self.stream, self.group, message_id)

    async def close(self) -> None:
        await self.client.aclose()

    def _decode(self, response: Any) -> tuple[StreamJob, ...]:
        jobs: list[StreamJob] = []
        for _, messages in response:
            jobs.extend(self._job(message_id, fields) for message_id, fields in messages)
        return tuple(jobs)

    @staticmethod
    def _job(message_id: str, fields: dict[str, str]) -> StreamJob:
        return StreamJob(
            message_id=str(message_id),
            event_id=fields["event_id"],
            event_type=fields["event_type"],
            payload=json.loads(fields["payload"]),
        )
