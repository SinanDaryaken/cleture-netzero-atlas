import asyncio

from atlas.application.dispatcher import OutboxDispatcher
from atlas.config import get_settings
from atlas.infrastructure.database import Database
from atlas.infrastructure.database.repositories import AtlasRepository
from atlas.infrastructure.queue import RedisStreamQueue


async def main() -> None:
    settings = get_settings()
    database = Database(settings)
    queue = RedisStreamQueue(settings)
    dispatcher = OutboxDispatcher(AtlasRepository(database.sessions), queue)
    try:
        await dispatcher.run_forever()
    finally:
        await queue.close()
        await database.dispose()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
