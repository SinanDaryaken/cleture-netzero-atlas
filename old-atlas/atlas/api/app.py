import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal
from hmac import compare_digest
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from atlas.application import AtlasApplication
from atlas.application.bootstrap import bootstrap_repository
from atlas.config import Settings, get_settings
from atlas.domain.enums import (
    EnvironmentalEntityType,
    FactorIntendedUse,
    FactorValueKind,
    SourceHistoryStrategy,
)
from atlas.domain.models import SourceDefinition
from atlas.geography import GeographicCoverageEngine
from atlas.infrastructure.database.repositories import AtlasRepository
from atlas.infrastructure.database.session import Database
from atlas.ingestion.registry import SourceNotFoundError, SourceRegistry
from atlas.matching import FactorMatchingEngine, MatchRequest, MatchResponse
from atlas.ports.storage import ObjectStorage
from atlas.product_readiness import product_readiness
from atlas.recommendation import (
    RecommendationEngine,
    RecommendationRequest,
    RecommendationResponse,
)
from atlas.search import SearchRequest, SearchResponse, SemanticSearchEngine
from atlas.semantics import ConceptLabel, OpenAITranslationProvider, SemanticRegistry
from atlas.units import ConversionParameter, ConversionRequest, ConversionResult, UnitEngine


def default_registry() -> SourceRegistry:
    project_root = Path(__file__).resolve().parents[2]
    return SourceRegistry.discover(project_root / "sources")


class ReviewDecisionRequest(BaseModel):
    decided_by: str = Field(min_length=1, max_length=255)
    note: str | None = Field(default=None, max_length=4000)


class ConceptResolveRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    language: str | None = Field(default=None, pattern=r"^[a-z]{2}$")
    limit: int = Field(default=5, ge=1, le=20)


class TranslationJobRequest(BaseModel):
    target_language: str = Field(pattern=r"^(en|tr|de|fr|es|ru|ar)$")
    requested_by: str = Field(min_length=1, max_length=255)
    only_missing: bool = True
    batch_size: int = Field(default=50, ge=1, le=50)
    execution_mode: Literal["batch", "responses"] = "batch"


class TranslationEditRequest(BaseModel):
    label: str = Field(min_length=1, max_length=255)
    definition: str | None = Field(default=None, max_length=2000)


class GlossaryEntryRequest(BaseModel):
    source_term: str = Field(min_length=1, max_length=255)
    target_language: str = Field(pattern=r"^(en|tr|de|fr|es|ru|ar)$")
    target_term: str | None = Field(default=None, max_length=255)
    domain: str = Field(default="environmental", min_length=1, max_length=128)
    protected: bool = False
    version: str = Field(default="1.0.0", min_length=1, max_length=64)


class SourceRunRequest(BaseModel):
    reference_year: int | None = Field(default=None, ge=1900, le=2200)


class ExplorerCalculateRequest(BaseModel):
    factor_id: str = Field(min_length=1, max_length=512)
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=128)
    country: str = Field(min_length=2, max_length=64)
    context: str = Field(min_length=1, max_length=64)
    calculation_profile: str = Field(min_length=1, max_length=128)
    year: int | None = Field(default=None, ge=1900, le=2200)
    allow_geographic_proxy: bool = False
    conversion_parameters: tuple[ConversionParameter, ...] = ()


class ExplorerCompareRequest(BaseModel):
    mode: Literal["unit", "context", "geography"]
    activity: str = Field(min_length=1, max_length=255)
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=128)
    country: str = Field(default="TR", min_length=2, max_length=64)
    context: str = Field(min_length=1, max_length=64)
    calculation_profile: str = Field(min_length=1, max_length=128)
    year: int | None = Field(default=None, ge=1900, le=2200)


class FacilityUpsertRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    country_code: str = Field(pattern=r"^[A-Za-z]{2}$")
    region: str | None = Field(default=None, max_length=128)
    electricity_connection_level: Literal["distribution", "transmission"] | None = None
    industry_codes: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    registry_version: str = Field(min_length=1, max_length=64)
    active: bool = True


class ConversionParameterCreateRequest(BaseModel):
    name: Literal["calorific_value", "density", "distance", "exchange_rate", "load", "occupancy"]
    value: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=128)
    source: str = Field(min_length=1, max_length=2000)
    country_code: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    facility_code: str | None = Field(default=None, min_length=1, max_length=128)
    valid_from: date | None = None
    valid_to: date | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    version: str = Field(min_length=1, max_length=64)


def create_app(
    registry: SourceRegistry | None = None,
    *,
    repository: AtlasRepository | None = None,
    settings: Settings | None = None,
    database: Database | None = None,
    storage: ObjectStorage | None = None,
) -> FastAPI:
    source_registry = registry or default_registry()
    runtime_settings = settings or get_settings()
    application = AtlasApplication(repository) if repository is not None else None
    geography_engine = GeographicCoverageEngine(runtime_settings.geography_config_path)
    unit_engine = UnitEngine()
    semantic_registry = SemanticRegistry()
    matching_engine = FactorMatchingEngine(geography_engine, semantic_registry, unit_engine)
    search_engine = SemanticSearchEngine(semantic_registry, unit_engine, geography_engine)
    recommendation_engine = RecommendationEngine(geography_engine, unit_engine)

    def openai_translation_provider() -> OpenAITranslationProvider:
        if runtime_settings.openai_api_key is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OPENAI_API_KEY is not configured",
            )
        return OpenAITranslationProvider(
            api_key=runtime_settings.openai_api_key.get_secret_value(),
            translation_model=runtime_settings.openai_translation_model,
            qa_model=runtime_settings.openai_qa_model,
            organization=runtime_settings.openai_organization,
            project=runtime_settings.openai_project,
        )

    async def resolve_runtime_concept(
        data: AtlasRepository,
        query: str,
        language: str | None,
        *,
        limit: int = 5,
    ) -> dict[str, Any]:
        if runtime_settings.multilingual_resolver_v2 and hasattr(data, "resolve_concepts"):
            return await data.resolve_concepts(query, language=language, limit=limit)
        legacy = semantic_registry.resolve_concept(query)
        candidates = []
        if legacy.concept_code:
            candidates.append(
                {
                    "concept_code": legacy.concept_code,
                    "family": legacy.concept_code.split(".", 1)[0],
                    "language": legacy.detected_language or language or "en",
                    "matched_term": query,
                    "term_kind": "legacy",
                    "match_type": "legacy_registry",
                    "score": round(legacy.confidence * 100),
                }
            )
        return {
            "query": query,
            "detected_language": legacy.detected_language,
            "script": "unknown",
            "normalized_query": legacy.normalized_query,
            "folded_query": legacy.normalized_query,
            "tokens": legacy.normalized_query.split(),
            "status": "resolved" if candidates else "unresolved",
            "candidates": candidates,
        }

    async def resolve_query_country(data: AtlasRepository, query: str) -> dict[str, Any] | None:
        resolver = getattr(data, "resolve_country_query", None)
        if callable(resolver):
            resolution = await resolver(query)
            if resolution is not None:
                return dict(resolution)
        fallback = geography_engine.extract_query_geography(query)
        return fallback.model_dump(mode="json") if fallback is not None else None

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        runtime_settings.validate_runtime_security()
        if repository is not None:
            await bootstrap_repository(repository)
        if storage is not None:
            await storage.ensure_buckets()
        yield
        if database is not None:
            await database.dispose()

    app = FastAPI(
        title="Cleture Atlas API",
        version="0.1.0",
        description="Published environmental data and source control API.",
        lifespan=lifespan,
    )
    explorer_root = Path(__file__).resolve().parents[1] / "explorer"
    app.mount(
        "/explorer/assets",
        StaticFiles(directory=explorer_root),
        name="explorer-assets",
    )

    @app.get("/explorer", include_in_schema=False, response_class=FileResponse)
    async def explorer() -> FileResponse:
        return FileResponse(explorer_root / "index.html")

    @app.get("/explorer/catalog", include_in_schema=False, response_class=FileResponse)
    async def factor_catalog() -> FileResponse:
        return FileResponse(explorer_root / "catalog.html")

    def require_repository() -> AtlasRepository:
        if repository is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="persistence is not configured",
            )
        return repository

    def require_application() -> AtlasApplication:
        if application is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="persistence is not configured",
            )
        return application

    def require_admin_key(
        key: Annotated[str | None, Header(alias="X-Atlas-Admin-Key")] = None,
    ) -> None:
        if key is None or not compare_digest(key, runtime_settings.admin_api_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid admin key",
            )

    async def explorer_match(
        request: MatchRequest,
        data: AtlasRepository,
    ) -> MatchResponse:
        geography_codes = geography_engine.search_codes(request.country)
        profile = semantic_registry.profile(request.calculation_profile)
        if request.context is not None and profile.context != request.context:
            raise ValueError("calculation profile does not belong to requested context")
        resolution = semantic_registry.resolve_concept(request.activity)
        candidates = await data.matching_candidates(
            activity=request.activity,
            activity_terms=resolution.search_terms,
            geography_codes=geography_codes,
            include_geographic_proxies=request.allow_geographic_proxy,
            entity_types=profile.allowed_entity_types,
            factor_value_kinds=profile.allowed_factor_value_kinds,
            intended_uses=profile.allowed_intended_uses,
        )
        return matching_engine.match(request, candidates)

    def explorer_calculation(
        factor: dict[str, Any],
        *,
        quantity: Decimal,
        unit: str,
        parameters: tuple[ConversionParameter, ...] = (),
    ) -> dict[str, Any]:
        target_unit = str(factor["activity_unit"])
        conversion = unit_engine.convert(
            ConversionRequest(
                mode="activity",
                value=quantity,
                from_unit=unit,
                to_unit=target_unit,
                parameters=parameters,
            )
        )
        result: dict[str, Any] | None = None
        if conversion.output_value is not None:
            result_value = conversion.output_value * Decimal(str(factor["factor_value"]))
            try:
                result_unit = unit_engine.parse(str(factor["factor_unit"])).numerator.code
            except LookupError:
                result_unit = str(factor["factor_unit"]).split("/", 1)[0]
            result = {"value": result_value, "unit": result_unit}
        recommendations: list[dict[str, Any]] = []
        return {
            "status": (
                "calculated"
                if result is not None
                else "conversion_parameter_required"
                if conversion.required_parameters
                else "incompatible"
            ),
            "factor": factor,
            "activity": {
                "original_value": quantity,
                "original_unit": unit,
                "normalized_value": conversion.output_value,
                "normalized_unit": target_unit,
            },
            "conversion": conversion.model_dump(mode="json"),
            "required_parameters": list(conversion.required_parameters),
            "recommended_parameters": recommendations,
            "result": result,
        }

    def factor_compatibility(factor: dict[str, Any]) -> dict[str, Any]:
        target = str(factor["activity_unit"])
        direct: list[str] = []
        parameterized: list[dict[str, str]] = []
        unsupported: list[str] = []
        for definition in unit_engine.definitions():
            probe = unit_engine.convert(
                ConversionRequest(
                    mode="activity", value=1, from_unit=definition.code, to_unit=target
                )
            )
            if probe.output_value is not None:
                direct.append(definition.code)
            elif probe.required_parameters:
                parameter = probe.required_parameters[0]
                source_definition = unit_engine.definition(definition.code)
                parameter_unit = {
                    "distance": "km",
                    "load": "tonne",
                    "occupancy": "passenger",
                    "exchange_rate": "dimensionless",
                }.get(parameter)
                if parameter == "calorific_value":
                    parameter_unit = f"{target}/{definition.code}"
                elif parameter == "density":
                    parameter_unit = (
                        f"{target}/{definition.code}"
                        if source_definition.dimension == "volume"
                        else f"{definition.code}/{target}"
                    )
                parameterized.append(
                    {
                        "unit": definition.code,
                        "parameter": parameter,
                        "parameter_unit": parameter_unit or "dimensionless",
                    }
                )
            else:
                unsupported.append(definition.code)
        return {
            "factor_id": factor["factor_id"],
            "native_activity_unit": target,
            "required_dimension": unit_engine.definition(target).dimension,
            "direct": sorted(direct),
            "parameterized": sorted(parameterized, key=lambda item: item["unit"]),
            "unsupported": sorted(unsupported),
            "unit_registry_version": unit_engine.version,
        }

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "atlas-api",
            "openai": {
                "configured": runtime_settings.openai_api_key is not None,
                "translation_model": runtime_settings.openai_translation_model,
                "qa_model": runtime_settings.openai_qa_model,
            },
        }

    @app.get("/ready", tags=["system"])
    async def ready(
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> JSONResponse:
        result = await product_readiness(data)
        return JSONResponse(
            content=result,
            status_code=(
                status.HTTP_200_OK if result["ready"] else status.HTTP_503_SERVICE_UNAVAILABLE
            ),
        )

    @app.get("/v1/units", tags=["units"])
    async def list_units() -> dict[str, Any]:
        return {
            "registry_version": unit_engine.version,
            "items": [item.model_dump(mode="json") for item in unit_engine.definitions()],
        }

    @app.get("/v1/units/{code}", tags=["units"])
    async def get_unit(code: str) -> dict[str, Any]:
        try:
            definition = unit_engine.definition(code)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        exact = [
            item.code
            for item in unit_engine.definitions()
            if item.dimension == definition.dimension and item.qualifiers == definition.qualifiers
        ]
        return {
            **definition.model_dump(mode="json"),
            "registry_version": unit_engine.version,
            "exact_conversions": exact,
        }

    @app.post("/v1/convert", response_model=ConversionResult, tags=["units"])
    async def convert_units(request: ConversionRequest) -> ConversionResult:
        return unit_engine.convert(request)

    @app.get("/v1/contexts", tags=["semantics"])
    async def list_contexts() -> dict[str, Any]:
        return {
            "policy_version": semantic_registry.version,
            "items": [
                {
                    "context": context,
                    "default_profile": semantic_registry.default_profile(context).code,
                }
                for context in semantic_registry.contexts()
            ],
        }

    @app.get("/v1/contexts/{context}/profiles", tags=["semantics"])
    async def context_profiles(context: str) -> dict[str, Any]:
        profiles = [item for item in semantic_registry.profiles() if item.context == context]
        if not profiles:
            raise HTTPException(status_code=404, detail=f"unknown calculation context: {context}")
        return {
            "context": context,
            "policy_version": semantic_registry.version,
            "items": [item.model_dump(mode="json") for item in profiles],
        }

    @app.get("/v1/profiles/{profile}/rules", tags=["semantics"])
    async def profile_rules(profile: str) -> dict[str, Any]:
        try:
            rules = semantic_registry.profile(profile)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        payload = {
            **rules.model_dump(mode="json"),
            "policy_version": semantic_registry.version,
        }
        if recommendation_engine.policy.profile_scope(profile) == "scope_3":
            payload["scope3_categories"] = (
                recommendation_engine.policy.scope3_category_catalog()
            )
        return payload

    @app.get("/v1/scope3/categories", tags=["recommendations"])
    async def scope3_categories() -> dict[str, Any]:
        return {
            "policy_version": recommendation_engine.policy.version,
            "items": recommendation_engine.policy.scope3_category_catalog(),
        }

    @app.get("/v1/concepts", tags=["semantics"])
    async def list_concepts(
        data: Annotated[AtlasRepository, Depends(require_repository)],
        language: str | None = Query(default=None, pattern=r"^[a-z]{2}$"),
    ) -> list[dict[str, Any]]:
        return await data.list_concepts(language=language)

    @app.post("/v1/concepts/resolve", tags=["semantics"])
    async def resolve_concept(
        request: ConceptResolveRequest,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        return await resolve_runtime_concept(
            data, request.text, request.language, limit=request.limit
        )

    @app.post(
        "/v1/admin/concepts/{concept_code}/labels",
        dependencies=[Depends(require_admin_key)],
        tags=["admin", "semantics"],
    )
    async def upsert_concept_label(
        concept_code: str,
        label: ConceptLabel,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        try:
            return await data.upsert_concept_label(
                concept_code,
                label,
                registry_version=semantic_registry.version,
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/v1/search", response_model=SearchResponse, tags=["search"])
    async def search_factors(
        request: SearchRequest,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> SearchResponse:
        try:
            effective_request = request
            effective_query = request.query
            if request.geography is None:
                query_geography = await resolve_query_country(data, request.query)
                if query_geography is not None:
                    effective_query = query_geography["search_query"] or request.query
                    effective_request = request.model_copy(
                        update={
                            "query": effective_query,
                            "geography": query_geography["geography_code"],
                        }
                    )
            profile = (
                semantic_registry.profile(effective_request.calculation_profile)
                if effective_request.calculation_profile
                else semantic_registry.default_profile(effective_request.context)
            )
            if profile.context != effective_request.context:
                raise ValueError("calculation profile does not belong to requested context")
            geography_codes = (
                geography_engine.search_codes(effective_request.geography)
                if effective_request.geography
                else ()
            )
            resolution = await resolve_runtime_concept(
                data, effective_query, effective_request.language, limit=5
            )
            concept_codes = tuple(
                str(item["concept_code"]) for item in resolution.get("candidates", [])
            )
            candidates = await data.search_candidates(
                query=effective_query,
                concept_codes=concept_codes,
                geography_codes=geography_codes,
                entity_types=profile.allowed_entity_types,
                factor_value_kinds=profile.allowed_factor_value_kinds,
                intended_uses=profile.allowed_intended_uses,
                reference_year=effective_request.year,
                limit=1000,
            )
            if request.include_ineligible:
                broad_candidates = await data.search_candidates(
                    query=effective_query,
                    geography_codes=geography_codes,
                    reference_year=effective_request.year,
                    limit=1000,
                )
                candidates_by_id = {
                    str(candidate.get("factor_id")): candidate for candidate in candidates
                }
                for candidate in broad_candidates:
                    candidates_by_id.setdefault(str(candidate.get("factor_id")), candidate)
                candidates = list(candidates_by_id.values())
            response = search_engine.search(
                effective_request,
                candidates,
                query_concepts=concept_codes,
            )
            return response.model_copy(update={"query": request.query})
        except (LookupError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post(
        "/v1/recommendations",
        response_model=RecommendationResponse,
        tags=["recommendations"],
    )
    async def recommend_factor(
        request: RecommendationRequest,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> RecommendationResponse:
        try:
            facility_id = request.facility_context.facility_id
            if facility_id:
                facility = await data.get_facility(facility_id)
                if facility is None:
                    raise LookupError(f"unknown facility: {facility_id}")
                if request.facility_context.country.upper() != facility["country_code"]:
                    raise ValueError("facility and request country do not match")
                request = request.model_copy(
                    update={
                        "facility_context": request.facility_context.model_copy(
                            update={
                                "country": facility["country_code"],
                                "region": facility["region"],
                                "electricity_connection_level": facility[
                                    "electricity_connection_level"
                                ],
                                "industry_codes": facility["industry_codes"],
                            }
                        )
                    }
                )
            parameter_catalog = getattr(data, "conversion_parameters", None)
            if not request.conversion_parameters and callable(parameter_catalog):
                effective_on = date(request.year, 12, 31) if request.year else date.today()
                catalog = await parameter_catalog(
                    country_code=request.facility_context.country,
                    facility_code=facility_id,
                    effective_on=effective_on,
                    review_status="approved",
                    limit=20,
                )
                preferred: dict[str, dict[str, Any]] = {}
                for item in catalog:
                    preferred.setdefault(str(item["name"]), item)
                request = request.model_copy(
                    update={
                        "conversion_parameters": tuple(
                            ConversionParameter(
                                name=item["name"],
                                value=item["value"],
                                unit=item["unit"],
                                source=(f"reviewed catalog {item['id']} · {item['source']}"),
                                valid_from=item["valid_from"],
                                valid_to=item["valid_to"],
                            )
                            for item in preferred.values()
                        )
                    }
                )
            profile = semantic_registry.profile(request.calculation_profile)
            if profile.context != request.context:
                raise ValueError("calculation profile does not belong to requested context")
            geography_codes = (
                ()
                if request.accept_proxy
                else geography_engine.search_codes(request.facility_context.country)
            )
            resolution = await resolve_runtime_concept(
                data, request.activity.text, request.language, limit=5
            )
            resolved = resolution.get("candidates") or []
            if resolution.get("status") == "ambiguous" and request.mode == "strict":
                return RecommendationResponse(
                    status="needs_input",
                    policy_version=recommendation_engine.policy.version,
                    intent={
                        "family_code": "unknown",
                        "concept_code": None,
                        "calculation_role": "unknown",
                        "scope_category": None,
                        "activity_basis": "unknown",
                        "qualifiers": {},
                    },
                    questions=(
                        {
                            "field": "activity.text",
                            "message": "The activity matches multiple canonical concepts.",
                            "options": [item["concept_code"] for item in resolved],
                        },
                    ),
                    trace=({"step": "concept", "status": "warning", "detail": resolution},),
                )
            concept_code = str(resolved[0]["concept_code"]) if resolved else None
            policy_match = recommendation_engine.policy.family_for_concept(concept_code)
            if policy_match is None:
                family_code, _ = recommendation_engine.policy.resolve_family(request.activity.text)
            else:
                family_code, _ = policy_match
            classification_prefixes = recommendation_engine.policy.classification_hints(
                family_code,
                request.activity.text,
                request.activity.classification_codes,
            )
            candidates = await data.recommendation_candidates(
                query=request.activity.text,
                family_code=family_code,
                policy_version=recommendation_engine.policy.version,
                classification_prefixes=classification_prefixes,
                geography_codes=geography_codes,
                reference_year=request.year,
                limit=2000,
            )
            return recommendation_engine.recommend(
                request,
                candidates,
                resolved_concept_code=concept_code,
            )
        except (LookupError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/v1/sources", response_model=list[SourceDefinition], tags=["sources"])
    async def list_sources() -> list[SourceDefinition]:
        return list(source_registry.list())

    @app.get("/v1/sources/{code}", response_model=SourceDefinition, tags=["sources"])
    async def get_source(code: str) -> SourceDefinition:
        try:
            return source_registry.get(code)
        except SourceNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"source not found: {code.upper()}",
            ) from error

    @app.get("/v1/sources/{code}/history", tags=["sources"])
    async def get_source_history(code: str) -> dict[str, Any]:
        try:
            source = source_registry.get(code)
        except SourceNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"source not found: {code.upper()}",
            ) from error
        policy = source.history
        payload = {
            "source_code": source.code,
            **policy.model_dump(mode="json"),
        }
        if policy.strategy == SourceHistoryStrategy.YEARLY_SUBMISSION:
            payload["submission_years"] = list(policy.reference_years)
        else:
            payload["reference_years"] = list(policy.reference_years)
        return payload

    @app.get("/v1/sources/{code}/coverage", tags=["sources"])
    async def source_coverage(
        code: str,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        try:
            source = source_registry.get(code)
        except SourceNotFoundError as error:
            raise HTTPException(
                status_code=404, detail=f"source not found: {code.upper()}"
            ) from error
        factors = await data.coverage_candidates(source_code=source.code)
        counts: dict[str, int] = {}
        for factor in factors:
            fit = str(factor["geographic_fit_type"])
            counts[fit] = counts.get(fit, 0) + 1
        return {
            "source_code": source.code,
            "declared_coverage": [item.model_dump(mode="json") for item in source.coverage],
            "published_factor_coverage": counts,
            "total_published_match_factors": len(factors),
        }

    @app.get("/v1/sources/{code}/historical-coverage", tags=["sources"])
    async def source_historical_coverage(
        code: str,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        try:
            source = source_registry.get(code)
        except SourceNotFoundError as error:
            raise HTTPException(
                status_code=404, detail=f"source not found: {code.upper()}"
            ) from error
        versions = await data.source_history_versions(source.code)
        expected_years = set(source.history.reference_years)
        ingested_years = {
            int(item["release_year"]) for item in versions if item["release_year"] is not None
        }
        covered_years = sorted(expected_years & ingested_years)
        completeness = len(covered_years) / len(expected_years) if expected_years else None
        if source.history.strategy == SourceHistoryStrategy.YEARLY_SUBMISSION:
            inventory_minima = [
                int(item["metrics"]["reference_year_min"])
                for item in versions
                if item.get("metrics", {}).get("reference_year_min") is not None
            ]
            inventory_maxima = [
                int(item["metrics"]["reference_year_max"])
                for item in versions
                if item.get("metrics", {}).get("reference_year_max") is not None
            ]
            submission_versions = []
            for item in versions:
                version = dict(item)
                version["submission_year"] = version.pop("release_year")
                version.pop("reference_year", None)
                submission_versions.append(version)
            return {
                "source_code": source.code,
                "strategy": source.history.strategy,
                "year_dimension": "submission_year",
                "expected_submission_years": sorted(expected_years),
                "ingested_submission_years": sorted(ingested_years),
                "missing_submission_years": sorted(expected_years - ingested_years),
                "historical_completeness": completeness,
                "inventory_reference_year_min": (
                    min(inventory_minima) if inventory_minima else None
                ),
                "inventory_reference_year_max": (
                    max(inventory_maxima) if inventory_maxima else None
                ),
                "snapshot_count": len(versions),
                "versions": submission_versions,
            }
        return {
            "source_code": source.code,
            "strategy": source.history.strategy,
            "year_dimension": "reference_year",
            "expected_reference_years": sorted(expected_years),
            "ingested_reference_years": sorted(ingested_years),
            "missing_reference_years": sorted(expected_years - ingested_years),
            "historical_completeness": completeness,
            "snapshot_count": len(versions),
            "versions": versions,
        }

    @app.post(
        "/v1/admin/sources/{code}/runs",
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[Depends(require_admin_key)],
        tags=["admin"],
    )
    async def request_source_run(
        code: str,
        service: Annotated[AtlasApplication, Depends(require_application)],
        request_body: Annotated[SourceRunRequest | None, Body()] = None,
    ) -> dict[str, Any]:
        if not runtime_settings.source_ingestion_enabled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="source ingestion is disabled by the intelligence-first policy",
            )
        reference_year = request_body.reference_year if request_body is not None else None
        try:
            request = await service.request_source_run(code, "manual", reference_year)
        except LookupError as error:
            raise HTTPException(
                status_code=404,
                detail=f"source not found: {code.upper()}",
            ) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "run_id": str(request.run_id),
            "status": "queued",
            "created": request.created,
            "run_mode": "historical_backfill" if reference_year is not None else "latest",
            "requested_reference_year": reference_year,
        }

    @app.get(
        "/v1/admin/runs/{run_id}",
        dependencies=[Depends(require_admin_key)],
        tags=["admin"],
    )
    async def get_run(
        run_id: UUID,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        run = await data.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        return run

    @app.get(
        "/v1/admin/reviews",
        dependencies=[Depends(require_admin_key)],
        tags=["admin"],
    )
    async def list_reviews(
        data: Annotated[AtlasRepository, Depends(require_repository)],
        review_status: str = Query(default="pending", alias="status"),
    ) -> list[dict[str, Any]]:
        return await data.list_reviews(review_status)

    @app.post(
        "/v1/admin/reviews/{review_id}/approve",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(require_admin_key)],
        tags=["admin"],
    )
    async def approve_review(
        review_id: UUID,
        service: Annotated[AtlasApplication, Depends(require_application)],
        decision: Annotated[ReviewDecisionRequest, Body()],
    ) -> None:
        try:
            await service.approve_review(
                review_id, decided_by=decision.decided_by, note=decision.note
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail="review not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post(
        "/v1/admin/reviews/{review_id}/reject",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(require_admin_key)],
        tags=["admin"],
    )
    async def reject_review(
        review_id: UUID,
        service: Annotated[AtlasApplication, Depends(require_application)],
        decision: Annotated[ReviewDecisionRequest, Body()],
    ) -> None:
        try:
            await service.reject_review(
                review_id, decided_by=decision.decided_by, note=decision.note
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail="review not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/v1/datasets", tags=["datasets"])
    async def list_datasets(
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> list[dict[str, Any]]:
        return await data.list_datasets()

    @app.get("/v1/datasets/{dataset_id}", tags=["datasets"])
    async def get_dataset(
        dataset_id: UUID,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        dataset = await data.get_dataset(dataset_id)
        if dataset is None:
            raise HTTPException(status_code=404, detail="dataset not found")
        return dataset

    @app.get("/v1/datasets/{dataset_id}/versions", tags=["datasets"])
    async def dataset_versions(
        dataset_id: UUID,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> list[dict[str, Any]]:
        return await data.dataset_versions(dataset_id)

    @app.get("/v1/factors", tags=["factors"])
    async def list_factors(
        data: Annotated[AtlasRepository, Depends(require_repository)],
        limit: int = Query(default=50, ge=1, le=200),
        cursor: str | None = None,
        query: str | None = Query(default=None, max_length=255),
        source: str | None = None,
        taxonomy: str | None = None,
        geography: str | None = None,
        origin_geography: str | None = None,
        reference_year: int | None = None,
        entity_type: EnvironmentalEntityType | None = None,
        emission_factors_only: bool = False,
        factor_records_only: bool = False,
        factor_value_kind: FactorValueKind | None = None,
        intended_use: FactorIntendedUse | None = None,
        scope: Literal["scope_1", "scope_2", "scope_3", "unspecified"] | None = None,
        sector: str | None = Query(default=None, max_length=64),
        category: str | None = Query(default=None, max_length=64),
        country: str | None = None,
        mode: str = Query(default="current", pattern="^(current|as_known_at)$"),
        known_at: datetime | None = None,
    ) -> dict[str, Any]:
        if mode == "as_known_at" and known_at is None:
            raise HTTPException(
                status_code=422,
                detail="known_at is required when mode=as_known_at",
            )
        if mode == "current" and known_at is not None:
            mode = "as_known_at"
        geography_codes: tuple[str, ...] = ()
        query_resolution = None
        concept_resolution = None
        concept_codes: tuple[str, ...] = ()
        if query and country is None and geography is None:
            query_resolution = await resolve_query_country(data, query)
            if query_resolution is not None:
                query = query_resolution["search_query"] or None
                geography = query_resolution["geography_code"]
        if query:
            concept_resolution = await resolve_runtime_concept(data, query, None)
            candidates = concept_resolution.get("candidates", [])
            if concept_resolution.get("status") == "resolved" and candidates:
                top_score = int(candidates[0].get("score", 0))
                score_floor = max(90, top_score - 5)
                concept_codes = tuple(
                    dict.fromkeys(
                        str(candidate["concept_code"])
                        for candidate in candidates
                        if int(candidate.get("score", 0)) >= score_floor
                    )
                )
            concept_resolution = {
                **concept_resolution,
                "applied_concept_codes": list(concept_codes),
            }
        if country:
            country_resolver = getattr(data, "resolve_country_code", None)
            if callable(country_resolver):
                resolved_country = await country_resolver(country)
                if resolved_country is not None:
                    country = str(resolved_country["code"])
            try:
                geography_codes = geography_engine.search_codes(country)
            except LookupError as error:
                raise HTTPException(status_code=404, detail=str(error)) from error
        catalog_entity_types: tuple[EnvironmentalEntityType, ...] = ()
        if entity_type is None:
            if factor_records_only:
                catalog_entity_types = (
                    EnvironmentalEntityType.EMISSION_FACTOR,
                    EnvironmentalEntityType.IMPLIED_EMISSION_FACTOR,
                    EnvironmentalEntityType.EMBODIED_EMISSION_FACTOR,
                    EnvironmentalEntityType.LCA_RESULT,
                )
            elif emission_factors_only:
                catalog_entity_types = (
                    EnvironmentalEntityType.EMISSION_FACTOR,
                    EnvironmentalEntityType.IMPLIED_EMISSION_FACTOR,
                    EnvironmentalEntityType.EMBODIED_EMISSION_FACTOR,
                )
        items = await data.list_published_factors(
            limit=limit + 1,
            cursor=cursor,
            query=query,
            concept_codes=concept_codes,
            source_code=source,
            taxonomy_code=taxonomy,
            geography_code=geography,
            origin_geography_code=origin_geography,
            reference_year=reference_year,
            entity_type=entity_type,
            entity_types=catalog_entity_types,
            factor_value_kind=factor_value_kind,
            intended_use=intended_use,
            scope=scope,
            sector_code=sector,
            category_code=category,
            geography_codes=geography_codes,
            known_at=known_at if mode == "as_known_at" else None,
        )
        has_more = len(items) > limit
        visible = items[:limit]
        if country:
            visible = [
                {
                    **item,
                    "geographic_coverage": geography_engine.evaluate(country, item).model_dump(
                        mode="json"
                    ),
                }
                for item in visible
                if geography_engine.evaluate(country, item).eligible
            ]
        return {
            "items": visible,
            "next_cursor": visible[-1]["cursor"] if has_more and visible else None,
            "query_resolution": query_resolution,
            "concept_resolution": concept_resolution,
        }

    @app.get("/v1/sectors", tags=["sectors"])
    async def list_sectors(
        data: Annotated[AtlasRepository, Depends(require_repository)],
        language: str = Query(default="en", pattern=r"^(en|tr)$"),
    ) -> dict[str, Any]:
        items = await data.list_sectors(language=language)
        return {
            "registry_version": items[0]["registry_version"] if items else None,
            "language": language,
            "items": items,
        }

    @app.get("/v1/countries", tags=["geographies"])
    async def list_countries(
        data: Annotated[AtlasRepository, Depends(require_repository)],
        language: str = Query(default="en", pattern=r"^[a-z]{2}$"),
    ) -> dict[str, Any]:
        items = await data.list_countries(language=language)
        return {
            "registry_version": items[0]["registry_version"] if items else None,
            "language": language,
            "items": items,
        }

    @app.get("/v1/facilities", tags=["facilities"])
    async def list_facilities(
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        items = await data.list_facilities()
        return {
            "registry_version": items[0]["registry_version"] if items else None,
            "items": items,
        }

    @app.get("/v1/facilities/{facility_code}", tags=["facilities"])
    async def get_facility(
        facility_code: str,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        facility = await data.get_facility(facility_code)
        if facility is None:
            raise HTTPException(status_code=404, detail="facility not found")
        return facility

    @app.put(
        "/v1/admin/facilities/{facility_code}",
        dependencies=[Depends(require_admin_key)],
        tags=["admin", "facilities"],
    )
    async def upsert_facility(
        facility_code: str,
        request: FacilityUpsertRequest,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        try:
            return await data.upsert_facility(code=facility_code, **request.model_dump())
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/v1/conversion-parameters", tags=["units", "facilities"])
    async def list_conversion_parameters(
        data: Annotated[AtlasRepository, Depends(require_repository)],
        name: str | None = Query(default=None, max_length=64),
        country: str | None = Query(default=None, pattern=r"^[A-Za-z]{2}$"),
        facility: str | None = Query(default=None, max_length=128),
        effective_on: date | None = None,
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> dict[str, Any]:
        return {
            "items": await data.conversion_parameters(
                name=name,
                country_code=country,
                facility_code=facility,
                effective_on=effective_on or date.today(),
                review_status="approved",
                limit=limit,
            )
        }

    @app.post(
        "/v1/admin/conversion-parameters",
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_admin_key)],
        tags=["admin", "units", "facilities"],
    )
    async def create_conversion_parameter(
        request: ConversionParameterCreateRequest,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        try:
            return await data.create_conversion_parameter(**request.model_dump())
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post(
        "/v1/admin/conversion-parameters/{parameter_id}/{decision}",
        dependencies=[Depends(require_admin_key)],
        tags=["admin", "units", "facilities"],
    )
    async def review_conversion_parameter(
        parameter_id: UUID,
        decision: str,
        request: ReviewDecisionRequest,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        try:
            return await data.decide_conversion_parameter(
                parameter_id,
                decision=decision,
                reviewed_by=request.decided_by,
                note=request.note,
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/v1/geographies", tags=["geographies"])
    async def list_geographies() -> dict[str, Any]:
        return {
            "configuration_version": geography_engine.config.version,
            "fit_scores": {
                fit.value: score for fit, score in geography_engine.config.fit_scores.items()
            },
            "items": [item.model_dump(mode="json") for item in geography_engine.list_geographies()],
        }

    @app.get("/v1/geographies/{country}/coverage", tags=["geographies"])
    async def geography_coverage(
        country: str,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        try:
            node = geography_engine.geography(country)
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        factors = await data.coverage_candidates()
        counts = {fit.value: 0 for fit in geography_engine.config.fallback_order}
        eligible = 0
        for factor in factors:
            evaluation = geography_engine.evaluate(node.code, factor)
            if not evaluation.eligible:
                continue
            eligible += 1
            counts[evaluation.geographic_fit.value] += 1
        return {
            "geography": node.model_dump(mode="json"),
            "coverage": counts,
            "total_available": eligible,
        }

    @app.get("/v1/explorer/concepts/resolve", tags=["explorer"])
    async def explorer_resolve_concept(
        data: Annotated[AtlasRepository, Depends(require_repository)],
        query: str = Query(min_length=1, max_length=255),
        language: str | None = Query(default=None, pattern=r"^[a-z]{2}$"),
    ) -> dict[str, Any]:
        return await resolve_runtime_concept(data, query, language)

    @app.post("/v1/explorer/compatibility", tags=["explorer"])
    async def explorer_factor_compatibility(
        factor_id: Annotated[str, Body(embed=True)],
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        factor = await data.get_published_factor(factor_id)
        if factor is None:
            raise HTTPException(status_code=404, detail="factor not found")
        try:
            return factor_compatibility(factor)
        except LookupError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/v1/explorer/calculate", tags=["explorer"])
    async def explorer_calculate(
        request: ExplorerCalculateRequest,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        factor = await data.get_published_factor(request.factor_id)
        if factor is None:
            raise HTTPException(status_code=404, detail="factor not found")
        try:
            profile_rules = semantic_registry.profile(request.calculation_profile)
            if profile_rules.context != request.context:
                raise ValueError("calculation profile does not belong to requested context")
            geography = geography_engine.evaluate(request.country, factor)
            if not geography.eligible and not request.allow_geographic_proxy:
                raise ValueError("selected factor requires explicit geographic proxy acceptance")
        except (LookupError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        calculation = explorer_calculation(
            factor,
            quantity=request.quantity,
            unit=request.unit,
            parameters=request.conversion_parameters,
        )
        calculation["decision"] = {
            "factor": factor,
            "eligibility": {
                "search_eligible": True,
                "calculation_eligible": True,
                "reason_codes": [],
                "profile": request.calculation_profile,
                "policy_version": recommendation_engine.policy.version,
            },
            "geographic_coverage": geography.model_dump(mode="json"),
        }
        return calculation

    @app.post("/v1/explorer/compare", tags=["explorer"])
    async def explorer_compare(
        request: ExplorerCompareRequest,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        variants: list[tuple[str, str, str]]
        if request.mode == "context":

            def selected_or_default(context: str, default_profile: str) -> str:
                return (
                    request.calculation_profile if request.context == context else default_profile
                )

            variants = [
                (
                    "Corporate Carbon",
                    request.country,
                    selected_or_default("corporate_carbon", "corporate_carbon.ghg_protocol.scope1"),
                ),
                ("CBAM", request.country, selected_or_default("cbam", "cbam.eu_definitive")),
                ("PCF", request.country, selected_or_default("pcf", "pcf.iso14067")),
                ("LCA", request.country, selected_or_default("lca", "lca.iso14040")),
            ]
        elif request.mode == "geography":
            variants = [
                ("Türkiye", "TR", request.calculation_profile),
                ("Germany", "DE", request.calculation_profile),
                ("France", "FR", request.calculation_profile),
            ]
        else:
            base = MatchRequest(
                activity=request.activity,
                country=request.country,
                context=request.context,
                calculation_profile=request.calculation_profile,
                year=request.year,
                activity_unit=request.unit,
                allow_geographic_proxy=True,
            )
            try:
                selected = (await explorer_match(base, data)).selected
            except LookupError as error:
                raise HTTPException(status_code=404, detail=str(error)) from error
            unit_variants = [
                (Decimal("12500"), "kWh"),
                (Decimal("12.5"), "MWh"),
                (Decimal("45"), "GJ"),
                (Decimal("45000"), "MJ"),
            ]
            return {
                "mode": request.mode,
                "items": [
                    {
                        "label": f"{value} {unit}",
                        **explorer_calculation(selected.factor, quantity=value, unit=unit),
                    }
                    for value, unit in unit_variants
                ],
            }

        items: list[dict[str, Any]] = []
        for label, country, profile_code in variants:
            variant_request = MatchRequest(
                activity=request.activity,
                country=country,
                context=semantic_registry.profile(profile_code).context,
                calculation_profile=profile_code,
                year=request.year,
                activity_unit=request.unit,
                allow_geographic_proxy=True,
            )
            try:
                match = await explorer_match(variant_request, data)
            except LookupError as error:
                items.append(
                    {
                        "label": label,
                        "country": country,
                        "calculation_profile": profile_code,
                        "status": "no_eligible_data",
                        "reason": str(error),
                    }
                )
                continue
            calculation = explorer_calculation(
                match.selected.factor,
                quantity=request.quantity,
                unit=request.unit,
            )
            items.append(
                {
                    "label": label,
                    "country": country,
                    "calculation_profile": profile_code,
                    "status": calculation["status"],
                    "selected": match.selected.model_dump(mode="json"),
                    "calculation": calculation,
                }
            )
        return {"mode": request.mode, "items": items}

    @app.post("/v1/explorer/regression/run", tags=["explorer"])
    async def explorer_regression_run(
        data: Annotated[AtlasRepository, Depends(require_repository)],
        requested_by: Annotated[
            str, Header(alias="X-Atlas-Actor", min_length=1, max_length=255)
        ] = "explorer",
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []

        def record(case_id: str, passed: bool, actual: str, expected: str) -> None:
            results.append(
                {
                    "id": case_id,
                    "status": "passed" if passed else "failed",
                    "actual": actual,
                    "expected": expected,
                }
            )

        def conversion(case_id: str, value: str, source: str, target: str, expected: str) -> None:
            output = unit_engine.convert(
                ConversionRequest(
                    mode="activity", value=Decimal(value), from_unit=source, to_unit=target
                )
            )
            record(
                case_id,
                output.output_value == Decimal(expected),
                str(output.output_value),
                expected,
            )

        conversion("TC-000001", "45", "GJ", "GJ", "45")
        conversion("TC-000002", "12500", "kWh", "GJ", "45")
        conversion("TC-000003", "25000", "l", "m3", "25.000")
        conditional = unit_engine.convert(
            ConversionRequest(mode="activity", value=1000, from_unit="m3", to_unit="GJ")
        )
        record(
            "TC-000004",
            conditional.required_parameters == ("calorific_value",),
            ",".join(conditional.required_parameters),
            "calorific_value",
        )
        record(
            "TC-000005",
            conditional.output_value is None,
            "no implicit recommendation used",
            "reviewed parameter required",
        )
        record("TC-000006", conditional.output_value is None, str(conditional.output_value), "None")
        impossible = unit_engine.convert(
            ConversionRequest(mode="activity", value=1, from_unit="TRY", to_unit="GJ")
        )
        record(
            "TC-000007",
            impossible.status.value == "incompatible",
            impossible.status.value,
            "incompatible",
        )
        languages = ["Natural gas", "Doğal gaz", "Erdgas", "Gaz naturel"]
        concepts = [semantic_registry.resolve_concept(item).concept_code for item in languages]
        record(
            "TC-000008",
            len(set(concepts)) == 1 and concepts[0] == "energy.natural_gas",
            ", ".join(str(item) for item in concepts),
            "energy.natural_gas",
        )
        exact_geo = geography_engine.evaluate(
            "TR",
            {
                "geographic_fit_type": "country_specific",
                "applicable_geographies": [{"code": "TR"}],
                "geography_level": "country",
            },
        )
        global_geo = geography_engine.evaluate(
            "TR",
            {
                "geographic_fit_type": "global",
                "applicable_geographies": [{"code": "GLOBAL"}],
                "geography_level": "global",
            },
        )
        record(
            "TC-000009",
            exact_geo.fallback_rank < global_geo.fallback_rank,
            f"{exact_geo.fallback_rank} < {global_geo.fallback_rank}",
            "country before global",
        )
        record(
            "TC-000010",
            global_geo.eligible and global_geo.fallback_used,
            str(global_geo.warning),
            "explicit global fallback",
        )
        lca_factor = {
            "entity_type": "lca_result",
            "factor_value_kind": "co2e_total",
            "intended_use": "characterization",
        }
        cbam_factor = {
            "entity_type": "embodied_emission_factor",
            "factor_value_kind": "co2e_total",
            "intended_use": "calculation_input",
        }
        cbam_lca = semantic_registry.evaluate("cbam.eu_definitive", lca_factor)
        lca_cbam = semantic_registry.evaluate("lca.iso14040", cbam_factor)
        record(
            "TC-000011",
            not cbam_lca.calculation_eligible,
            ",".join(cbam_lca.reason_codes),
            "LCA rejected by CBAM",
        )
        record(
            "TC-000012",
            not lca_cbam.calculation_eligible,
            ",".join(lca_cbam.reason_codes),
            "CBAM rejected by LCA",
        )
        equivalents = [
            unit_engine.convert(
                ConversionRequest(mode="activity", value=value, from_unit=unit, to_unit="GJ")
            ).output_value
            for value, unit in ((12500, "kWh"), (Decimal("12.5"), "MWh"), (45, "GJ"), (45000, "MJ"))
        ]
        record(
            "TC-000013",
            all(item == Decimal("45") for item in equivalents),
            ", ".join(str(item) for item in equivalents),
            "45 GJ each",
        )
        wheat_request = MatchRequest(
            activity="Buğday",
            quantity=100,
            activity_unit="kg",
            country="TR",
            context="pcf",
            calculation_profile="pcf.iso14067",
            year=2025,
            allow_geographic_proxy=True,
        )
        try:
            wheat = await explorer_match(wheat_request, data)
            wheat_geography = wheat.selected.geographic_coverage.factor_geography
            record(
                "TC-000014",
                wheat.concept_resolution is not None
                and wheat.concept_resolution.get("concept_code") == "agriculture.wheat"
                and wheat.selected.geographic_coverage.fallback_used,
                f"{wheat.selected.factor['name']} · {wheat_geography}",
                "wheat PCF factor with explicit geography decision",
            )
        except (LookupError, ValueError) as error:
            record("TC-000014", False, str(error), "wheat PCF factor")
        electricity_request = SearchRequest(
            query="Elektrik",
            context="corporate_carbon",
            calculation_profile="corporate_carbon.ghg_protocol.scope2_location",
            geography="TR",
            year=2025,
            limit=100,
        )
        try:
            geography_codes = geography_engine.search_codes("TR")
            electricity_candidates = await data.search_candidates(
                query=electricity_request.query,
                geography_codes=geography_codes,
                limit=200,
            )
            electricity = search_engine.search(electricity_request, electricity_candidates)
            eligible_electricity = [
                item for item in electricity.items if item.eligibility.calculation_eligible
            ]
            selected_geographies = [
                item.geographic_coverage.factor_geography
                for item in eligible_electricity
                if item.geographic_coverage is not None
            ]
            record(
                "TC-000015",
                bool(eligible_electricity)
                and "TR" in selected_geographies
                and set(selected_geographies) <= {"TR", "GLOBAL"},
                ", ".join(selected_geographies) or "no eligible electricity factor",
                "TR exact factors followed only by GLOBAL fallback",
            )
        except (LookupError, ValueError) as error:
            record("TC-000015", False, str(error), "TR + GLOBAL only")
        cbam_electricity_request = SearchRequest(
            query="Electricity",
            context="cbam",
            calculation_profile="cbam.eu_definitive",
            geography="TR",
            year=2025,
            limit=100,
        )
        try:
            geography_codes = geography_engine.search_codes("TR")
            cbam_candidates = await data.search_candidates(
                query=cbam_electricity_request.query,
                geography_codes=geography_codes,
                limit=200,
            )
            cbam_electricity = search_engine.search(cbam_electricity_request, cbam_candidates)
            record(
                "TC-000016",
                not cbam_electricity.items,
                f"{len(cbam_electricity.items)} calculation-eligible factors",
                "0 inventory electricity factors in CBAM",
            )
        except (LookupError, ValueError) as error:
            record("TC-000016", False, str(error), "CBAM electricity isolation")
        passenger_missing = unit_engine.convert(
            ConversionRequest(
                mode="activity", value=2, from_unit="passenger", to_unit="passenger.km"
            )
        )
        passenger_converted = unit_engine.convert(
            ConversionRequest(
                mode="activity",
                value=2,
                from_unit="passenger",
                to_unit="passenger.km",
                parameters=(
                    ConversionParameter(
                        name="distance",
                        value=500,
                        unit="km",
                        source="regression itinerary",
                    ),
                ),
            )
        )
        record(
            "TC-000017",
            passenger_missing.required_parameters == ("distance",)
            and passenger_converted.output_value == Decimal("1000"),
            (
                f"required={','.join(passenger_missing.required_parameters)}; "
                f"normalized={passenger_converted.output_value} passenger.km"
            ),
            "distance required; 2 passenger x 500 km = 1000 passenger.km",
        )
        diesel_request = SearchRequest(
            query="diesel",
            context="corporate_carbon",
            calculation_profile="corporate_carbon.ghg_protocol.scope1",
            geography="TR",
            year=2025,
            unit="kg",
            limit=100,
        )
        try:
            diesel_profile = semantic_registry.profile(diesel_request.calculation_profile or "")
            diesel_candidates = await data.search_candidates(
                query=diesel_request.query,
                geography_codes=geography_engine.search_codes("TR"),
                entity_types=diesel_profile.allowed_entity_types,
                factor_value_kinds=diesel_profile.allowed_factor_value_kinds,
                intended_uses=diesel_profile.allowed_intended_uses,
                reference_year=2025,
                limit=1000,
            )
            diesel = search_engine.search(diesel_request, diesel_candidates)
            ipcc_derived = [
                item
                for item in diesel.items
                if item.factor.get("source_code") == "GHG_PROTOCOL"
                and "ipcc"
                in str(
                    ((item.factor.get("methodology") or {}).get("details") or {}).get(
                        "original_source", ""
                    )
                ).casefold()
            ]
            record(
                "TC-000018",
                bool(diesel.items) and bool(ipcc_derived),
                ", ".join(str(item.factor.get("source_code")) for item in diesel.items),
                "TR totals plus a GHG Protocol IPCC-derived diesel total",
            )
        except (LookupError, ValueError) as error:
            record("TC-000018", False, str(error), "Scope 1 diesel factors")

        baseline_profiles = (
            (
                "Scope 1 natural gas",
                "corporate_carbon.ghg_protocol.scope1",
                "Natural gas",
                "m3",
                "scope_1",
            ),
            (
                "Scope 2 electricity",
                "corporate_carbon.ghg_protocol.scope2_location",
                "Electricity",
                "kWh",
                "scope_2",
            ),
        )
        recommendation_semaphore = asyncio.Semaphore(8)

        async def limited_recommendation(
            request: RecommendationRequest,
        ) -> RecommendationResponse:
            async with recommendation_semaphore:
                return await recommend_factor(request, data)

        async def baseline_case(
            facility_index: int,
            profile_index: int,
            profile: tuple[str, str, str, str, str],
        ) -> tuple[str, bool, str, str]:
            facility_code = f"FAC-{facility_index:03d}"
            facility = await data.get_facility(facility_code)
            (
                label,
                profile_code,
                activity_text,
                activity_unit,
                expected_scope,
            ) = profile
            case_id = f"TC-{19 + ((facility_index - 1) * 2) + profile_index:06d}"
            expected = (
                f"{label}: recommended kgCO2e with "
                + (
                    "the facility country or GLOBAL combustion fallback"
                    if expected_scope == "scope_1"
                    else "an exact facility-country electricity factor"
                )
            )
            if facility is None:
                return case_id, False, f"missing facility {facility_code}", expected
            country = str(facility["country_code"])
            baseline_request = RecommendationRequest.model_validate(
                {
                    "mode": "suggest",
                    "context": "corporate_carbon",
                    "calculation_profile": profile_code,
                    "year": 2025,
                    "facility_context": {
                        "facility_id": facility_code,
                        "country": country,
                    },
                    "activity": {
                        "text": activity_text,
                        "quantity": 100,
                        "unit": activity_unit,
                    },
                }
            )
            try:
                baseline_response = await limited_recommendation(baseline_request)
                candidate = baseline_response.recommended
                calculation = baseline_response.calculation
                if candidate is None:
                    return case_id, False, baseline_response.status, expected
                factor_geography = str(candidate.geography.get("factor_geography") or "")
                geography_is_safe = (
                    factor_geography in {country, "GLOBAL"}
                    if expected_scope == "scope_1"
                    else factor_geography == country
                    and bool(candidate.geography.get("exact_geography"))
                )
                passed = (
                    baseline_response.status == "recommended"
                    and baseline_response.intent.scope_category == expected_scope
                    and candidate.applicability.get("scope_category") == expected_scope
                    and geography_is_safe
                    and calculation is not None
                    and calculation.result_value is not None
                    and calculation.result_unit == "kgCO2e"
                )
                result_value = calculation.result_value if calculation else None
                result_unit = calculation.result_unit if calculation else ""
                actual = (
                    f"{candidate.factor.get('source_code')} · {factor_geography} · "
                    f"{candidate.rank.tier} · {result_value} {result_unit}"
                )
                return case_id, passed, actual, expected
            except (HTTPException, LookupError, ValueError) as error:
                detail = error.detail if isinstance(error, HTTPException) else str(error)
                return case_id, False, str(detail), expected

        baseline_results = await asyncio.gather(
            *(
                baseline_case(facility_index, profile_index, profile)
                for facility_index in range(1, 21)
                for profile_index, profile in enumerate(baseline_profiles)
            )
        )
        for baseline_result in baseline_results:
            record(*baseline_result)

        scope3_catalog = recommendation_engine.policy.scope3_category_catalog()
        record(
            "TC-000059",
            [item["code"] for item in scope3_catalog] == list(range(1, 16))
            and any(item["availability"] == "not_supported" for item in scope3_catalog),
            f"{len(scope3_catalog)} categories with explicit availability",
            "GHG Protocol categories 1-15 with explicit availability",
        )

        async def scope3_recommendation_case(
            case_id: str,
            *,
            facility_code: str,
            country: str,
            category: int,
            text: str,
            quantity: int,
            unit: str,
            expected_status: str,
            expected_source: str,
            qualifiers: dict[str, str] | None = None,
        ) -> None:
            expected = (
                f"Scope 3 category {category} · {expected_status} · {expected_source}"
            )
            scope3_request = RecommendationRequest.model_validate(
                {
                    "mode": "suggest",
                    "context": "corporate_carbon",
                    "calculation_profile": "corporate_carbon.ghg_protocol.scope3",
                    "year": 2025,
                    "facility_context": {
                        "facility_id": facility_code,
                        "country": country,
                    },
                    "activity": {
                        "text": text,
                        "quantity": quantity,
                        "unit": unit,
                        "scope3_category": category,
                        "qualifiers": qualifiers or {},
                    },
                }
            )
            try:
                response = await limited_recommendation(scope3_request)
                candidate = response.recommended
                actual_source = (
                    str(candidate.factor.get("source_code")) if candidate else "none"
                )
                passed = (
                    response.status == expected_status
                    and response.intent.scope3_category == category
                    and candidate is not None
                    and candidate.applicability.get("scope_category") == "scope_3"
                    and category in candidate.applicability.get("scope3_categories", ())
                    and actual_source == expected_source
                )
                actual = (
                    f"category {response.intent.scope3_category} · {response.status} · "
                    f"{actual_source}"
                )
                record(case_id, passed, actual, expected)
            except (HTTPException, LookupError, ValueError) as error:
                detail = error.detail if isinstance(error, HTTPException) else str(error)
                record(case_id, False, str(detail), expected)

        await scope3_recommendation_case(
            "TC-000060",
            facility_code="FAC-001",
            country="TR",
            category=1,
            text="education service",
            quantity=100,
            unit="TRY",
            expected_status="conversion_parameter_required",
            expected_source="OPEN_CEDA",
        )
        await scope3_recommendation_case(
            "TC-000061",
            facility_code="FAC-006",
            country="GB",
            category=3,
            text="natural gas WTT",
            quantity=100,
            unit="m3",
            expected_status="recommended",
            expected_source="DEFRA",
        )
        await scope3_recommendation_case(
            "TC-000062",
            facility_code="FAC-004",
            country="US",
            category=4,
            text="road freight",
            quantity=100,
            unit="tonne.km",
            expected_status="recommended",
            expected_source="EPA",
        )
        await scope3_recommendation_case(
            "TC-000063",
            facility_code="FAC-004",
            country="US",
            category=5,
            text="waste landfill",
            quantity=100,
            unit="kg",
            expected_status="recommended",
            expected_source="EPA",
            qualifiers={"material": "Aluminum Cans", "treatment": "landfill"},
        )
        await scope3_recommendation_case(
            "TC-000064",
            facility_code="FAC-006",
            country="GB",
            category=6,
            text="domestic flight",
            quantity=100,
            unit="passenger.km",
            expected_status="recommended",
            expected_source="DEFRA",
        )

        ambiguous_freight = await recommend_factor(
            RecommendationRequest.model_validate(
                {
                    "mode": "suggest",
                    "context": "corporate_carbon",
                    "calculation_profile": "corporate_carbon.ghg_protocol.scope3",
                    "year": 2025,
                    "facility_context": {"facility_id": "FAC-004", "country": "US"},
                    "activity": {
                        "text": "road freight",
                        "quantity": 100,
                        "unit": "tonne.km",
                    },
                }
            ),
            data,
        )
        ambiguous_options = (
            [item["code"] for item in ambiguous_freight.questions[0]["options"]]
            if ambiguous_freight.questions
            else []
        )
        record(
            "TC-000065",
            ambiguous_freight.status == "needs_input" and ambiguous_options == [4, 9],
            f"{ambiguous_freight.status} · {ambiguous_options}",
            "needs_input · [4, 9]",
        )
        await scope3_recommendation_case(
            "TC-000066",
            facility_code="FAC-004",
            country="US",
            category=9,
            text="road freight",
            quantity=100,
            unit="tonne.km",
            expected_status="recommended",
            expected_source="EPA",
        )
        await scope3_recommendation_case(
            "TC-000067",
            facility_code="FAC-004",
            country="US",
            category=12,
            text="waste landfill",
            quantity=100,
            unit="kg",
            expected_status="recommended",
            expected_source="EPA",
            qualifiers={"material": "Aluminum Cans", "treatment": "landfill"},
        )
        unsupported_investment = await recommend_factor(
            RecommendationRequest.model_validate(
                {
                    "mode": "suggest",
                    "context": "corporate_carbon",
                    "calculation_profile": "corporate_carbon.ghg_protocol.scope3",
                    "year": 2025,
                    "facility_context": {"facility_id": "FAC-001", "country": "TR"},
                    "activity": {
                        "text": "education service",
                        "quantity": 100,
                        "unit": "TRY",
                        "scope3_category": 15,
                    },
                }
            ),
            data,
        )
        unsupported_reason = (
            unsupported_investment.trace[-1].get("details", {}).get("reason")
            if unsupported_investment.trace
            else None
        )
        record(
            "TC-000068",
            unsupported_investment.status == "no_applicable_factor"
            and unsupported_reason == "family_category_mismatch",
            f"{unsupported_investment.status} · {unsupported_reason}",
            "category 15 coverage gap is explicit",
        )
        return await data.record_regression_run(
            suite_version="2026.08.30.2",
            requested_by=requested_by,
            results=results,
        )

    @app.get("/v1/explorer/regression/runs", tags=["explorer"])
    async def explorer_regression_runs(
        data: Annotated[AtlasRepository, Depends(require_repository)],
        limit: int = Query(default=50, ge=1, le=500),
    ) -> dict[str, Any]:
        return {"items": await data.regression_runs(limit=limit)}

    @app.get("/v1/explorer/regression/runs/{run_id}", tags=["explorer"])
    async def explorer_regression_run_detail(
        run_id: UUID,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        run = await data.get_regression_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="regression run not found")
        return run

    @app.post(
        "/v1/admin/regression/runs/{run_id}/{decision}",
        dependencies=[Depends(require_admin_key)],
        tags=["admin", "explorer"],
    )
    async def review_regression_run(
        run_id: UUID,
        decision: str,
        request: ReviewDecisionRequest,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        try:
            return await data.review_regression_run(
                run_id,
                decision=decision,
                reviewed_by=request.decided_by,
                note=request.note,
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get(
        "/v1/admin/units/inventory",
        dependencies=[Depends(require_admin_key)],
        tags=["admin", "units"],
    )
    async def unit_inventory(
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        return {"items": await data.unit_inventory()}

    @app.post(
        "/v1/admin/intelligence/rebuild",
        dependencies=[Depends(require_admin_key)],
        tags=["admin", "semantics"],
    )
    async def rebuild_intelligence(
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        return await data.rebuild_intelligence_index(unit_engine, semantic_registry)

    @app.get(
        "/v1/admin/intelligence/coverage",
        dependencies=[Depends(require_admin_key)],
        tags=["admin", "semantics", "units"],
    )
    async def intelligence_coverage(
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        return await data.intelligence_coverage(
            target_languages=semantic_registry.target_languages()
        )

    @app.post(
        "/v1/admin/sectors/rebuild",
        dependencies=[Depends(require_admin_key)],
        tags=["admin", "sectors"],
    )
    async def rebuild_sectors(
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        return await data.rebuild_sector_projection()

    @app.get(
        "/v1/admin/sectors/coverage",
        dependencies=[Depends(require_admin_key)],
        tags=["admin", "sectors"],
    )
    async def sector_coverage(
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        return await data.sector_projection_coverage()

    @app.get(
        "/v1/admin/translations",
        dependencies=[Depends(require_admin_key)],
        tags=["admin", "semantics"],
    )
    async def translation_reviews(
        data: Annotated[AtlasRepository, Depends(require_repository)],
        review_status: str = Query(
            default="draft", pattern="^(draft|approved|rejected|superseded)$"
        ),
        language: str | None = Query(default=None, pattern=r"^[a-z]{2}$"),
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
    ) -> dict[str, Any]:
        return {
            "items": await data.translation_reviews(
                review_status=review_status,
                language=language,
                limit=limit,
                offset=offset,
            )
        }

    @app.post(
        "/v1/admin/translations/{label_id}/{decision}",
        dependencies=[Depends(require_admin_key)],
        tags=["admin", "semantics"],
    )
    async def decide_translation_review(
        label_id: UUID,
        decision: str,
        request: ReviewDecisionRequest,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        try:
            return await data.decide_translation_review(
                label_id,
                decision=decision,
                reviewed_by=request.decided_by,
                note=request.note,
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.patch(
        "/v1/admin/translations/{label_id}",
        dependencies=[Depends(require_admin_key)],
        tags=["admin", "semantics"],
    )
    async def edit_translation_draft(
        label_id: UUID,
        request: TranslationEditRequest,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        try:
            return await data.edit_translation_draft(
                label_id,
                label=request.label,
                definition=request.definition,
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post(
        "/v1/admin/translation-rollouts/{language}/approve",
        dependencies=[Depends(require_admin_key)],
        tags=["admin", "semantics"],
    )
    async def approve_translation_rollout(
        language: str,
        request: ReviewDecisionRequest,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        if language not in semantic_registry.target_languages():
            raise HTTPException(status_code=422, detail="unsupported rollout language")
        try:
            return await data.approve_translation_rollout(
                language,
                reviewed_by=request.decided_by,
                note=request.note,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post(
        "/v1/admin/translation-jobs",
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[Depends(require_admin_key)],
        tags=["admin", "semantics"],
    )
    async def create_translation_job(
        request: TranslationJobRequest,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        if request.execution_mode == "batch" and not runtime_settings.openai_batch_enabled:
            raise HTTPException(status_code=409, detail="OpenAI Batch translation is disabled")
        inputs = await data.translation_inputs(
            target_language=request.target_language,
            only_missing=request.only_missing,
        )
        if not inputs:
            raise HTTPException(status_code=409, detail="no concepts require translation")
        glossary = await data.glossary_terms(target_language=request.target_language)
        glossary_version = await data.glossary_version(target_language=request.target_language)
        provider = openai_translation_provider()
        jobs: list[dict[str, Any]] = []
        failure: dict[str, Any] | None = None
        chunks = [
            inputs[offset : offset + request.batch_size]
            for offset in range(0, len(inputs), request.batch_size)
        ]
        for batch_index, chunk in enumerate(chunks, start=1):
            if request.execution_mode == "responses":
                try:
                    generation = await run_in_threadpool(
                        provider.generate_group,
                        chunk,
                        target_language=request.target_language,
                        glossary=glossary,
                    )
                except Exception as error:
                    failure = {
                        "batch_index": batch_index,
                        "stage": "responses_generation",
                        "message": str(error)[:1000],
                    }
                    break
                try:
                    job = await data.create_translation_job(
                        provider_job_id=generation.provider_job_id,
                        input_file_id=f"responses:{generation.provider_job_id}",
                        target_language=request.target_language,
                        model=provider.translation_model,
                        qa_model=provider.qa_model,
                        prompt_version=provider.prompt_version,
                        glossary_version=glossary_version,
                        custom_ids=generation.custom_ids,
                        requested_by=request.requested_by,
                    )
                    results = dict(generation.results)
                    source_inputs = {item.concept_code: item for item in chunk}
                    qa_reviewed = 0
                    qa_failed = 0
                    for custom_id, draft in tuple(results.items()):
                        concept_code = generation.custom_ids.get(custom_id)
                        source_input = source_inputs.get(str(concept_code))
                        repeated = len(draft.preferred_term.casefold().split()) != len(
                            set(draft.preferred_term.casefold().split())
                        )
                        unchanged = (
                            source_input is not None
                            and draft.preferred_term.casefold()
                            == source_input.canonical_name_en.casefold()
                            and request.target_language != "en"
                        )
                        if source_input is not None and (draft.warnings or repeated or unchanged):
                            try:
                                results[custom_id] = await run_in_threadpool(
                                    provider.generate,
                                    source_input,
                                    target_language=request.target_language,
                                    glossary=glossary,
                                    qa=True,
                                )
                                qa_reviewed += 1
                            except Exception:
                                qa_failed += 1
                    ingestion = await data.ingest_translation_results(
                        UUID(str(job["job_id"])), results
                    )
                    ingestion["sol_qa_reviewed"] = qa_reviewed
                    ingestion["sol_qa_failed"] = qa_failed
                    completed_job = await data.get_translation_job(UUID(str(job["job_id"])))
                    job = completed_job or job
                    job["ingestion"] = ingestion
                    jobs.append(job)
                except Exception as error:
                    failure = {
                        "batch_index": batch_index,
                        "stage": "local_persistence",
                        "provider_job_id": generation.provider_job_id,
                        "message": str(error)[:1000],
                    }
                    break
                continue
            try:
                submission = await run_in_threadpool(
                    provider.submit_batch,
                    chunk,
                    target_language=request.target_language,
                    glossary=glossary,
                )
            except Exception as error:
                failure = {
                    "batch_index": batch_index,
                    "stage": "provider_submission",
                    "message": str(error)[:1000],
                }
                break
            try:
                jobs.append(
                    await data.create_translation_job(
                        provider_job_id=submission.provider_job_id,
                        input_file_id=submission.input_file_id,
                        target_language=request.target_language,
                        model=provider.translation_model,
                        qa_model=provider.qa_model,
                        prompt_version=provider.prompt_version,
                        glossary_version=glossary_version,
                        custom_ids=submission.custom_ids,
                        requested_by=request.requested_by,
                    )
                )
            except Exception as error:
                cleanup_status = "cancel_failed"
                try:
                    cleanup_status = await run_in_threadpool(
                        provider.cancel_batch, submission.provider_job_id
                    )
                except Exception:
                    pass
                failure = {
                    "batch_index": batch_index,
                    "stage": "local_persistence",
                    "provider_job_id": submission.provider_job_id,
                    "cleanup_status": cleanup_status,
                    "message": str(error)[:1000],
                }
                break
        if not jobs and failure is not None:
            raise HTTPException(
                status_code=502,
                detail=f"OpenAI terminology generation failed: {failure['message']}",
            )
        return {
            "status": (
                "partial"
                if failure
                else "completed"
                if request.execution_mode == "responses"
                else "submitted"
            ),
            "target_language": request.target_language,
            "execution_mode": request.execution_mode,
            "batch_size": request.batch_size,
            "batch_count": len(jobs),
            "requested_count": sum(int(job["requested_count"]) for job in jobs),
            "remaining_count": len(inputs) - sum(int(job["requested_count"]) for job in jobs),
            "jobs": jobs,
            "failure": failure,
        }

    @app.get(
        "/v1/admin/translation-jobs",
        dependencies=[Depends(require_admin_key)],
        tags=["admin", "semantics"],
    )
    async def list_translation_jobs(
        data: Annotated[AtlasRepository, Depends(require_repository)],
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> dict[str, Any]:
        return {"items": await data.translation_jobs(limit=limit)}

    @app.post(
        "/v1/admin/translation-jobs/{job_id}/sync",
        dependencies=[Depends(require_admin_key)],
        tags=["admin", "semantics"],
    )
    async def sync_translation_job(
        job_id: UUID,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        job = await data.get_translation_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="translation job not found")
        if job["status"] == "review_required" and not str(job["provider_job_id"]).startswith(
            "resp_"
        ):
            return job
        provider = openai_translation_provider()
        try:
            if str(job["provider_job_id"]).startswith("resp_"):
                results = await run_in_threadpool(
                    provider.group_results,
                    str(job["provider_job_id"]),
                    dict(job.get("custom_ids") or {}),
                )
                ingestion = await data.ingest_translation_results(job_id, results)
                updated = await data.get_translation_job(job_id) or job
                updated["ingestion"] = {
                    **ingestion,
                    "recovered_from_response": True,
                }
                return updated
            provider_status = await run_in_threadpool(
                provider.batch_status, str(job["provider_job_id"])
            )
            counts = provider_status.get("request_counts") or {}
            updated = await data.update_translation_job(
                job_id,
                status=str(provider_status["status"]),
                output_file_id=provider_status.get("output_file_id"),
                error_file_id=provider_status.get("error_file_id"),
                completed_count=int(counts.get("completed", 0) or 0),
                failed_count=int(counts.get("failed", 0) or 0),
            )
            if provider_status["status"] == "completed" and provider_status.get("output_file_id"):
                results = await run_in_threadpool(
                    provider.batch_results, str(provider_status["output_file_id"])
                )
                glossary = await data.glossary_terms(target_language=str(job["target_language"]))
                source_inputs = {
                    item.concept_code: item
                    for item in await data.translation_inputs(
                        target_language=str(job["target_language"]),
                        only_missing=False,
                    )
                }
                qa_reviewed = 0
                for custom_id, draft in tuple(results.items()):
                    concept_code = (job.get("custom_ids") or {}).get(custom_id)
                    source_input = source_inputs.get(str(concept_code)) if concept_code else None
                    repeated = len(draft.preferred_term.casefold().split()) != len(
                        set(draft.preferred_term.casefold().split())
                    )
                    unchanged = (
                        source_input is not None
                        and draft.preferred_term.casefold()
                        == source_input.canonical_name_en.casefold()
                        and job["target_language"] != "en"
                    )
                    if source_input is not None and (draft.warnings or repeated or unchanged):
                        results[custom_id] = await run_in_threadpool(
                            provider.generate,
                            source_input,
                            target_language=str(job["target_language"]),
                            glossary=glossary,
                            qa=True,
                        )
                        qa_reviewed += 1
                ingestion = await data.ingest_translation_results(job_id, results)
                ingestion["sol_qa_reviewed"] = qa_reviewed
                updated = await data.get_translation_job(job_id) or updated
                updated["ingestion"] = ingestion
            return updated
        except (LookupError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            await data.update_translation_job(
                job_id,
                status="failed",
                error=str(error),
            )
            raise HTTPException(
                status_code=502, detail=f"OpenAI batch sync failed: {error}"
            ) from error

    @app.get(
        "/v1/admin/translation-glossary",
        dependencies=[Depends(require_admin_key)],
        tags=["admin", "semantics"],
    )
    async def list_translation_glossary(
        data: Annotated[AtlasRepository, Depends(require_repository)],
        language: str | None = Query(default=None, pattern=r"^[a-z]{2}$"),
    ) -> dict[str, Any]:
        return {"items": await data.list_glossary(target_language=language)}

    @app.post(
        "/v1/admin/translation-glossary",
        dependencies=[Depends(require_admin_key)],
        tags=["admin", "semantics"],
    )
    async def upsert_translation_glossary(
        request: GlossaryEntryRequest,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> dict[str, Any]:
        return await data.upsert_glossary_entry(**request.model_dump())

    @app.get("/v1/factors/{factor_id}/versions", tags=["factors"])
    async def factor_versions(
        factor_id: str,
        data: Annotated[AtlasRepository, Depends(require_repository)],
    ) -> list[dict[str, Any]]:
        return await data.factor_versions(factor_id)

    @app.get("/v1/factors/{factor_id}/provenance", tags=["factors"])
    async def factor_provenance(
        factor_id: str,
        data: Annotated[AtlasRepository, Depends(require_repository)],
        reference_year: int | None = Query(default=None, ge=1900, le=2200),
    ) -> dict[str, Any]:
        factor = await data.get_published_factor(factor_id, reference_year=reference_year)
        if factor is None:
            raise HTTPException(status_code=404, detail="factor not found")
        return {
            "factor_id": factor_id,
            "factor_version_id": factor.get("factor_version_id"),
            "provenance": factor.get("provenance", []),
        }

    @app.get("/v1/factors/{factor_id}/alternatives", tags=["factors", "matching"])
    async def factor_alternatives(
        factor_id: str,
        data: Annotated[AtlasRepository, Depends(require_repository)],
        calculation_profile: str = Query(min_length=1, max_length=128),
        country: str = Query(min_length=2, max_length=64),
    ) -> dict[str, Any]:
        factor = await data.get_published_factor(factor_id)
        if factor is None:
            raise HTTPException(status_code=404, detail="factor not found")
        try:
            profile = semantic_registry.profile(calculation_profile)
            geography_codes = geography_engine.search_codes(country)
        except LookupError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        request = MatchRequest(
            activity=str(factor.get("taxonomy_code") or factor.get("name")),
            country=country,
            year=factor.get("reference_year"),
            activity_unit=factor.get("activity_unit"),
            calculation_profile=calculation_profile,
        )
        candidates = await data.matching_candidates(
            activity=request.activity,
            geography_codes=geography_codes,
            entity_types=profile.allowed_entity_types,
            factor_value_kinds=profile.allowed_factor_value_kinds,
            intended_uses=profile.allowed_intended_uses,
        )
        candidates = [item for item in candidates if item.get("factor_id") != factor_id]
        if not candidates:
            return {"factor_id": factor_id, "items": []}
        try:
            response = matching_engine.match(request, candidates)
        except LookupError:
            return {"factor_id": factor_id, "items": []}
        return {
            "factor_id": factor_id,
            "items": [
                item.model_dump(mode="json") for item in (response.selected, *response.alternatives)
            ],
        }

    @app.get("/v1/factors/{factor_id}", tags=["factors"])
    async def get_factor(
        factor_id: str,
        data: Annotated[AtlasRepository, Depends(require_repository)],
        reference_year: int | None = Query(default=None, ge=1900, le=2200),
        mode: str = Query(default="current", pattern="^(current|as_known_at)$"),
        known_at: datetime | None = None,
    ) -> dict[str, Any]:
        if mode == "as_known_at" and known_at is None:
            raise HTTPException(
                status_code=422,
                detail="known_at is required when mode=as_known_at",
            )
        if mode == "current" and known_at is not None:
            mode = "as_known_at"
        factor = await data.get_published_factor(
            factor_id,
            reference_year=reference_year,
            known_at=known_at if mode == "as_known_at" else None,
        )
        if factor is None:
            raise HTTPException(status_code=404, detail="factor not found")
        return factor

    return app
