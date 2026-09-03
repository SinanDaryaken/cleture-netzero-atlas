from pathlib import Path

from atlas.infrastructure.database.repositories import AtlasRepository
from atlas.ingestion.registry import SourceRegistry
from atlas.semantics import SemanticRegistry
from atlas.units import UnitEngine

PROJECT_ROOT = Path(__file__).resolve().parents[2]


async def bootstrap_repository(repository: AtlasRepository) -> SourceRegistry:
    registry = SourceRegistry.discover(PROJECT_ROOT / "sources")
    await repository.sync_sources(registry.list())
    await repository.seed_intelligence(UnitEngine(), SemanticRegistry())
    return registry
