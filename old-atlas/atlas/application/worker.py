from __future__ import annotations

import asyncio
import socket
from uuid import UUID

from atlas.domain.enums import RunMode
from atlas.domain.models import PipelineRun
from atlas.infrastructure.database.repositories import AtlasRepository, SqlRunRepository
from atlas.infrastructure.queue import RedisStreamQueue, StreamJob
from atlas.ingestion.factory import AdapterFactory
from atlas.ingestion.registry import SourceRegistry
from atlas.orchestration import PipelineEngine
from atlas.ports.storage import ObjectStorage


class AtlasWorker:
    def __init__(
        self,
        *,
        repository: AtlasRepository,
        run_repository: SqlRunRepository,
        queue: RedisStreamQueue,
        storage: ObjectStorage,
        registry: SourceRegistry,
        consumer_name: str | None = None,
        ingestion_enabled: bool = False,
    ) -> None:
        self.repository = repository
        self.queue = queue
        self.storage = storage
        self.registry = registry
        self.ingestion_enabled = ingestion_enabled
        self.adapter_factory = AdapterFactory(repository=repository, storage=storage)
        self.engine = PipelineEngine(run_repository)
        self.consumer_name = consumer_name or f"{socket.gethostname()}-{id(self)}"

    async def run_forever(self) -> None:
        if not self.ingestion_enabled:
            await asyncio.Event().wait()
            return
        await self.queue.ensure_group()
        await self.storage.ensure_buckets()
        while True:
            jobs = await self.queue.reclaim_stale(self.consumer_name)
            if not jobs:
                jobs = await self.queue.read(self.consumer_name)
            for job in jobs:
                await self.process(job)

    async def process(self, job: StreamJob) -> None:
        if job.event_type != "source.run.requested":
            await self.queue.acknowledge(job.message_id)
            return
        if not self.ingestion_enabled:
            return
        run_id = UUID(job.payload["run_id"])
        source_code = str(job.payload["source_code"]).upper()
        attempt = int(job.payload.get("attempt", 1))
        run_mode = RunMode(str(job.payload.get("run_mode", RunMode.LATEST.value)))
        requested_reference_year = job.payload.get("requested_reference_year")
        async with self.repository.source_lock(source_code):
            source = self.registry.get(source_code)
            adapter = self.adapter_factory.create(source)
            try:
                context = await self.engine.execute(
                    source,
                    adapter,
                    run=PipelineRun(
                        id=run_id,
                        source_code=source_code,
                        run_mode=run_mode,
                        requested_reference_year=requested_reference_year,
                    ),
                    attempt=attempt,
                )
            finally:
                await adapter.close()
        if context.run.failure_retryable and attempt < source.ingestion.max_attempts:
            await self.repository.enqueue_retry(run_id, source_code, attempt)
        await self.queue.acknowledge(job.message_id)


async def run_worker_until_cancelled(worker: AtlasWorker) -> None:
    try:
        await worker.run_forever()
    except asyncio.CancelledError:
        raise
