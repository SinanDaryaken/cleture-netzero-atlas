import asyncio
import json
import sys

from atlas.config import get_settings
from atlas.infrastructure.database import Database
from atlas.infrastructure.database.repositories import AtlasRepository
from atlas.recommendation import RecommendationPolicy
from atlas.semantics import SemanticRegistry


async def rebuild() -> dict[str, object]:
    database = Database(get_settings())
    try:
        repository = AtlasRepository(database.sessions)
        semantics = SemanticRegistry()
        return await repository.rebuild_recommendation_projection(
            RecommendationPolicy(),
            profiles=tuple(profile.code for profile in semantics.profiles()),
        )
    finally:
        await database.dispose()


async def coverage() -> dict[str, object]:
    database = Database(get_settings())
    try:
        repository = AtlasRepository(database.sessions)
        return await repository.recommendation_projection_coverage(RecommendationPolicy())
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
