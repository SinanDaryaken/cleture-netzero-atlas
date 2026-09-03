import asyncio
import json
import sys

from atlas.config import get_settings
from atlas.infrastructure.database import Database
from atlas.infrastructure.database.repositories import AtlasRepository
from atlas.product_readiness import product_readiness


async def check() -> dict[str, object]:
    database = Database(get_settings())
    try:
        return await product_readiness(AtlasRepository(database.sessions))
    finally:
        await database.dispose()


def run() -> None:
    result = asyncio.run(check())
    print(json.dumps(result, sort_keys=True))
    if not bool(result["ready"]):
        sys.exit(1)


if __name__ == "__main__":
    run()
