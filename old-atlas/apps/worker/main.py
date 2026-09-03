import asyncio

from atlas.application.bootstrap import bootstrap_repository
from atlas.application.worker import AtlasWorker
from atlas.config import get_settings
from atlas.infrastructure.database import Database
from atlas.infrastructure.database.repositories import AtlasRepository, SqlRunRepository
from atlas.infrastructure.queue import RedisStreamQueue
from atlas.infrastructure.storage import S3ObjectStorage


async def main() -> None:
    settings = get_settings()
    settings.validate_runtime_security()
    database = Database(settings)
    repository = AtlasRepository(database.sessions)
    registry = await bootstrap_repository(repository)
    queue = RedisStreamQueue(settings)
    storage = S3ObjectStorage(settings)
    worker = AtlasWorker(
        repository=repository,
        run_repository=SqlRunRepository(database.sessions),
        queue=queue,
        storage=storage,
        registry=registry,
        ingestion_enabled=settings.source_ingestion_enabled,
    )
    try:
        await worker.run_forever()
    finally:
        await queue.close()
        await database.dispose()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
