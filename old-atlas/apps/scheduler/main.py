import asyncio

from atlas.application.bootstrap import bootstrap_repository
from atlas.config import get_settings
from atlas.infrastructure.database import Database
from atlas.infrastructure.database.repositories import AtlasRepository
from atlas.scheduling import AtlasScheduler


async def main() -> None:
    settings = get_settings()
    database = Database(settings)
    repository = AtlasRepository(database.sessions)
    registry = await bootstrap_repository(repository)
    scheduler = AtlasScheduler(
        repository,
        registry,
        poll_seconds=settings.scheduler_poll_seconds,
        ingestion_enabled=settings.source_ingestion_enabled,
    )
    try:
        await scheduler.run_forever()
    finally:
        await database.dispose()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
