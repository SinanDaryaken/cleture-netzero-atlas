from __future__ import annotations

from typing import Any

from atlas.infrastructure.database.repositories import AtlasRepository
from atlas.recommendation import RecommendationPolicy
from atlas.semantics import SemanticRegistry


async def product_readiness(repository: AtlasRepository) -> dict[str, Any]:
    semantics = SemanticRegistry()
    intelligence = await repository.intelligence_coverage(
        target_languages=semantics.target_languages()
    )
    recommendation = await repository.recommendation_projection_coverage(RecommendationPolicy())
    sectors = await repository.sector_projection_coverage()
    gates = {
        "intelligence": bool(intelligence["ready"]),
        "recommendation": bool(recommendation["ready"]),
        "sectors": bool(sectors["ready"]),
    }
    return {
        "ready": all(gates.values()),
        "gates": gates,
        "intelligence": intelligence,
        "recommendation": recommendation,
        "sectors": sectors,
    }
