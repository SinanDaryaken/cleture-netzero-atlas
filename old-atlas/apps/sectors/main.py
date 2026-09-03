import asyncio
import json
import sys

from atlas.config import get_settings
from atlas.infrastructure.database import Database
from atlas.infrastructure.database.repositories import AtlasRepository


async def rebuild() -> dict[str, object]:
    database = Database(get_settings())
    try:
        return await AtlasRepository(database.sessions).rebuild_sector_projection()
    finally:
        await database.dispose()


async def coverage() -> dict[str, object]:
    database = Database(get_settings())
    try:
        return await AtlasRepository(database.sessions).sector_projection_coverage()
    finally:
        await database.dispose()


async def ensure() -> dict[str, object]:
    current = await coverage()
    if bool(current["ready"]):
        return {"action": "unchanged", **current}
    rebuilt = await rebuild()
    return {"action": "rebuilt", **rebuilt}


def run() -> None:
    print(json.dumps(asyncio.run(rebuild()), sort_keys=True))


def run_check() -> None:
    result = asyncio.run(coverage())
    print(json.dumps(result, sort_keys=True))
    if not bool(result["ready"]):
        sys.exit(1)


def run_ensure() -> None:
    print(json.dumps(asyncio.run(ensure()), sort_keys=True))


if __name__ == "__main__":
    run()
