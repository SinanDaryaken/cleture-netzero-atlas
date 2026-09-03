from decimal import Decimal
from types import SimpleNamespace
from typing import Any, ClassVar, cast
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from atlas.api import create_app
from atlas.config import Settings
from atlas.semantics import TranslationDraft


def test_health_and_source_registry_api() -> None:
    client = TestClient(create_app())

    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert health["service"] == "atlas-api"
    assert health["openai"]["translation_model"] == "gpt-5.6-terra"

    response = client.get("/v1/sources")
    assert response.status_code == 200
    assert {source["code"] for source in response.json()} == {
        "ADEME",
        "AGRIBALYSE",
        "AIB",
        "CBAM",
        "CONCITO",
        "CANADA",
        "DEFRA",
        "EEA",
        "EMBER",
        "EPA",
        "ETKB",
        "GHG_PROTOCOL",
        "GLEC",
        "IPCC",
        "OPEN_CEDA",
        "OEKOBAUDAT",
        "PLASTICS_EUROPE",
        "PLASTICS_RECYCLERS_EUROPE",
        "UNFCCC_TUIK",
        "WRAP",
    }


def test_explorer_test_lab_and_assets_are_served_without_persistence() -> None:
    client = TestClient(create_app())

    explorer = client.get("/explorer")
    catalog = client.get("/explorer/catalog")
    script = client.get("/explorer/assets/app.js")
    catalog_script = client.get("/explorer/assets/catalog.js")
    styles = client.get("/explorer/assets/styles.css")
    catalog_styles = client.get("/explorer/assets/catalog.css")

    assert explorer.status_code == 200
    assert "Atlas Explorer" in explorer.text
    assert 'class="explorer-grid"' in explorer.text
    assert 'id="search-query"' in explorer.text
    assert 'id="search-quantity"' in explorer.text
    assert 'id="search-unit"' in explorer.text
    assert 'id="results-list"' in explorer.text
    assert 'id="factor-detail"' in explorer.text
    assert 'id="decision-detail"' in explorer.text
    assert 'id="test-lab-open"' in explorer.text
    assert 'id="test-lab-dialog"' in explorer.text
    assert 'data-lab-panel="pipeline"' in explorer.text
    assert 'data-lab-panel="suite"' in explorer.text
    assert 'data-lab-panel="languages"' in explorer.text
    assert 'data-lab-panel="coverage"' in explorer.text
    assert 'id="terminology-dialog"' in explorer.text
    assert 'id="terminology-create-job"' in explorer.text
    assert "data-tab=" not in explorer.text
    assert script.status_code == 200
    assert 'api("/v1/recommendations"' in script.text
    assert 'api("/v1/units")' in script.text
    assert "const grouped = new Map()" in script.text
    assert "<optgroup" in script.text
    assert "explorer/input-units?" not in script.text
    assert 'api("/v1/explorer/compatibility"' in script.text
    assert 'api("/v1/explorer/calculate"' in script.text
    assert 'api("/v1/convert"' in script.text
    assert "runLabCurrent" in script.text
    assert "runLabSuite" in script.text
    assert "runLanguageMatrix" in script.text
    assert 'api("/v1/admin/intelligence/coverage"' in script.text
    assert 'api("/v1/admin/translation-jobs"' in script.text
    assert 'api("/v1/admin/translation-glossary"' in script.text
    assert "batch_size: 50" in script.text
    assert "Start 50-item groups" in explorer.text
    assert 'id="conversion-unit"' in script.text
    assert "conversion-parameter-value" in script.text
    assert catalog.status_code == 200
    assert "Atlas Factor Catalog" in catalog.text
    assert "Factor &amp; LCA records" in catalog.text
    assert 'id="catalog-source"' in catalog.text
    assert 'id="catalog-scope"' in catalog.text
    assert 'id="catalog-query"' in catalog.text
    assert 'id="catalog-list"' in catalog.text
    assert 'id="catalog-year-breakdown"' in catalog.text
    assert 'id="catalog-detail-body"' in catalog.text
    assert catalog_script.status_code == 200
    assert 'factor_records_only: "true"' in catalog_script.text
    assert "api(`/v1/factors/${encodedId}${yearQuery}`)" in catalog_script.text
    assert "api(`/v1/factors/${encodedId}/versions`)" in catalog_script.text
    assert "renderYearBreakdown" in catalog_script.text
    assert "state.allItems.filter" in catalog_script.text
    assert "button[data-year]" in catalog_script.text
    assert catalog_styles.status_code == 200
    assert ".catalog-grid" in catalog_styles.text
    assert 'api("/v1/facilities")' in script.text
    assert 'api("/v1/scope3/categories")' in script.text
    assert "let FACILITIES = {}" in script.text
    assert 'facility()?.code || "TR"' in script.text
    assert 'api("/v1/countries?language=en"' in script.text
    assert 'api("/v1/match"' not in script.text
    assert 'api("/v1/resolve"' not in script.text
    assert 'id="scope3-category"' in explorer.text
    assert 'id="scope3-waste-material"' in explorer.text
    assert 'id="scope3-waste-treatment"' in explorer.text
    assert 'id="scope3-haul"' in explorer.text
    assert "scope3_category: input.scope3Category || undefined" in script.text
    assert "qualifiers: input.scope3Qualifiers" in script.text
    assert styles.status_code == 200
    assert "--signal: #c6ff3b" in styles.text
    assert ".explorer-grid .result-main strong" in styles.text
    assert ".explorer-grid .detail-list dd" in styles.text
    assert (
        "grid-template-columns: minmax(250px, 1fr) minmax(285px, 1fr) minmax(590px, 2fr)"
        in styles.text
    )


def test_unknown_source_returns_404() -> None:
    client = TestClient(create_app())

    response = client.get("/v1/sources/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "source not found: MISSING"


def test_source_history_exposes_declared_reference_years() -> None:
    client = TestClient(create_app())

    response = client.get("/v1/sources/AIB/history")

    assert response.status_code == 200
    assert response.json()["strategy"] == "lagged_yearly_release"
    assert response.json()["reference_years"] == [2020, 2021, 2022, 2023, 2024, 2025]
    assert response.json()["publication_lag_years"] == 1


def test_versioned_database_history_has_no_synthetic_annual_releases() -> None:
    client = TestClient(create_app())

    response = client.get("/v1/sources/IPCC/history")

    assert response.status_code == 200
    assert response.json()["strategy"] == "versioned_database"
    assert response.json()["reference_years"] == []


def test_admin_endpoints_require_key_before_persistence() -> None:
    client = TestClient(create_app())

    response = client.post("/v1/admin/sources/DEFRA/runs")

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid admin key"


class FactorRepositoryStub:
    def __init__(self) -> None:
        self.filters: dict[str, Any] = {}

    async def list_published_factors(self, **filters: Any) -> list[dict[str, Any]]:
        self.filters = filters
        return []


class MultilingualFactorRepositoryStub(FactorRepositoryStub):
    async def resolve_concepts(
        self,
        query: str,
        *,
        language: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        assert query == "T\u0131r"
        assert language is None
        assert limit == 5
        return {
            "query": query,
            "detected_language": "tr",
            "script": "latin",
            "normalized_query": "t\u0131r",
            "folded_query": "t\u0131r",
            "tokens": ["t\u0131r"],
            "status": "resolved",
            "candidates": [
                {
                    "concept_code": "transport.freight.road",
                    "family": "transport_mode",
                    "language": "tr",
                    "matched_term": "t\u0131r",
                    "term_kind": "synonym",
                    "match_type": "exact_alias",
                    "score": 99,
                }
            ],
        }


def test_factor_semantic_filters_are_forwarded() -> None:
    repository = FactorRepositoryStub()
    client = TestClient(create_app(repository=cast(Any, repository)))

    response = client.get(
        "/v1/factors?entity_type=emission_factor&"
        "factor_value_kind=non_co2_co2e&intended_use=inventory"
    )

    assert response.status_code == 200
    assert repository.filters["entity_type"] == "emission_factor"
    assert repository.filters["factor_value_kind"] == "non_co2_co2e"
    assert repository.filters["intended_use"] == "inventory"


def test_emission_factor_only_filters_are_forwarded() -> None:
    repository = FactorRepositoryStub()
    client = TestClient(create_app(repository=cast(Any, repository)))

    response = client.get(
        "/v1/factors?query=natural%20gas&source=GHG_PROTOCOL&"
        "scope=scope_1&emission_factors_only=true"
    )

    assert response.status_code == 200
    assert repository.filters["query"] == "natural gas"
    assert repository.filters["source_code"] == "GHG_PROTOCOL"
    assert repository.filters["scope"] == "scope_1"
    assert repository.filters["entity_types"] == (
        "emission_factor",
        "implied_emission_factor",
        "embodied_emission_factor",
    )


def test_factor_catalog_filters_include_published_lca_results() -> None:
    repository = FactorRepositoryStub()
    client = TestClient(create_app(repository=cast(Any, repository)))

    response = client.get("/v1/factors?query=wheat&source=AGRIBALYSE&factor_records_only=true")

    assert response.status_code == 200
    assert repository.filters["query"] == "wheat"
    assert repository.filters["source_code"] == "AGRIBALYSE"
    assert repository.filters["entity_types"] == (
        "emission_factor",
        "implied_emission_factor",
        "embodied_emission_factor",
        "lca_result",
    )


def test_factor_catalog_sector_filters_are_forwarded() -> None:
    repository = FactorRepositoryStub()
    client = TestClient(create_app(repository=cast(Any, repository)))

    response = client.get("/v1/factors?factor_records_only=true&sector=energy&category=electricity")

    assert response.status_code == 200
    assert repository.filters["sector_code"] == "energy"
    assert repository.filters["category_code"] == "electricity"


def test_factor_catalog_applies_multilingual_concept_resolution() -> None:
    repository = MultilingualFactorRepositoryStub()
    client = TestClient(create_app(repository=cast(Any, repository)))

    response = client.get("/v1/factors?query=T%C4%B1r&factor_records_only=true")

    assert response.status_code == 200
    assert repository.filters["query"] == "T\u0131r"
    assert repository.filters["concept_codes"] == ("transport.freight.road",)
    assert response.json()["concept_resolution"]["applied_concept_codes"] == [
        "transport.freight.road"
    ]


def test_factor_catalog_extracts_country_name_as_exact_geography_filter() -> None:
    repository = FactorRepositoryStub()
    client = TestClient(create_app(repository=cast(Any, repository)))

    response = client.get("/v1/factors?query=banana%20Denmark&factor_records_only=true")

    assert response.status_code == 200
    assert repository.filters["query"] == "banana"
    assert repository.filters["geography_code"] == "DK"
    assert response.json()["query_resolution"] == {
        "original_query": "banana Denmark",
        "search_query": "banana",
        "geography_code": "DK",
        "geography_name": "Denmark",
        "matched_alias": "denmark",
    }


def test_unknown_factor_catalog_scope_is_rejected() -> None:
    client = TestClient(create_app(repository=cast(Any, FactorRepositoryStub())))

    response = client.get("/v1/factors?scope=scope_4")

    assert response.status_code == 422


def test_unknown_factor_semantic_filter_is_rejected() -> None:
    client = TestClient(create_app(repository=cast(Any, FactorRepositoryStub())))

    response = client.get("/v1/factors?factor_value_kind=ordinary")

    assert response.status_code == 422


def test_unknown_environmental_entity_type_is_rejected() -> None:
    client = TestClient(create_app(repository=cast(Any, FactorRepositoryStub())))

    response = client.get("/v1/factors?entity_type=spreadsheet_row")

    assert response.status_code == 422


def test_as_known_at_factor_query_forwards_system_time() -> None:
    repository = FactorRepositoryStub()
    client = TestClient(create_app(repository=cast(Any, repository)))

    response = client.get("/v1/factors?mode=as_known_at&known_at=2024-12-31T23:59:59Z")

    assert response.status_code == 200
    assert repository.filters["known_at"].isoformat() == "2024-12-31T23:59:59+00:00"


def test_as_known_at_requires_timestamp() -> None:
    client = TestClient(create_app(repository=cast(Any, FactorRepositoryStub())))

    response = client.get("/v1/factors?mode=as_known_at")

    assert response.status_code == 422
    assert response.json()["detail"] == "known_at is required when mode=as_known_at"


class DatasetVersionsRepositoryStub(FactorRepositoryStub):
    async def dataset_versions(self, dataset_id: object) -> list[dict[str, Any]]:
        return [{"id": str(dataset_id), "version_status": "current"}]


def test_dataset_version_history_endpoint() -> None:
    dataset_id = uuid4()
    client = TestClient(create_app(repository=cast(Any, DatasetVersionsRepositoryStub())))

    response = client.get(f"/v1/datasets/{dataset_id}/versions")

    assert response.status_code == 200
    assert response.json() == [{"id": str(dataset_id), "version_status": "current"}]


class HistoricalRunRepositoryStub(FactorRepositoryStub):
    def __init__(self) -> None:
        super().__init__()
        self.requested_reference_year: int | None = None

    async def request_run(
        self,
        source_code: str,
        requested_by: str,
        requested_reference_year: int | None = None,
    ) -> SimpleNamespace:
        self.filters = {"source_code": source_code, "requested_by": requested_by}
        self.requested_reference_year = requested_reference_year
        return SimpleNamespace(run_id=UUID(int=1), created=True)

    async def source_history_versions(self, source_code: str) -> list[dict[str, Any]]:
        self.filters = {"source_code": source_code}
        return [
            {
                "id": str(UUID(int=2)),
                "version_key": "2024-v1",
                "release_year": 2024,
                "reference_year": 2024,
                "source_published_at": None,
                "retrieved_at": "2026-08-28T00:00:00Z",
                "workflow_status": "review_required",
                "version_status": "candidate",
                "checksum": "a" * 64,
                "parser_version": "0.1.0",
                "mapping_version": "0.1.0",
                "metrics": {"reference_year_min": 1990, "reference_year_max": 2022},
            }
        ]


def test_admin_can_request_a_reference_year_backfill() -> None:
    repository = HistoricalRunRepositoryStub()
    settings = Settings(_env_file=None, source_ingestion_enabled=True)
    client = TestClient(create_app(repository=cast(Any, repository), settings=settings))

    response = client.post(
        "/v1/admin/sources/DEFRA/runs",
        headers={"X-Atlas-Admin-Key": "replace-this-local-admin-key"},
        json={"reference_year": 2022},
    )

    assert response.status_code == 202
    assert response.json()["run_mode"] == "historical_backfill"
    assert response.json()["requested_reference_year"] == 2022
    assert repository.requested_reference_year == 2022


def test_source_ingestion_is_disabled_by_default() -> None:
    repository = HistoricalRunRepositoryStub()
    client = TestClient(create_app(repository=cast(Any, repository)))

    response = client.post(
        "/v1/admin/sources/DEFRA/runs",
        headers={"X-Atlas-Admin-Key": "replace-this-local-admin-key"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "source ingestion is disabled by the intelligence-first policy"
    )


def test_historical_coverage_reports_missing_annual_releases() -> None:
    repository = HistoricalRunRepositoryStub()
    client = TestClient(create_app(repository=cast(Any, repository)))

    response = client.get("/v1/sources/EPA/historical-coverage")

    assert response.status_code == 200
    assert response.json()["ingested_reference_years"] == [2024]
    assert response.json()["missing_reference_years"] == [2020, 2021, 2022, 2023, 2025]
    assert response.json()["historical_completeness"] == 1 / 6


def test_national_submission_history_does_not_alias_submission_as_reference_year() -> None:
    repository = HistoricalRunRepositoryStub()
    client = TestClient(create_app(repository=cast(Any, repository)))

    history = client.get("/v1/sources/UNFCCC_TUIK/history")
    coverage = client.get("/v1/sources/UNFCCC_TUIK/historical-coverage")

    assert history.status_code == 200
    assert history.json()["submission_years"] == list(range(2020, 2027))
    assert "reference_years" not in history.json()
    assert coverage.status_code == 200
    assert coverage.json()["year_dimension"] == "submission_year"
    assert coverage.json()["ingested_submission_years"] == [2024]
    assert coverage.json()["inventory_reference_year_min"] == 1990
    assert coverage.json()["inventory_reference_year_max"] == 2022
    assert coverage.json()["versions"][0]["submission_year"] == 2024
    assert "reference_year" not in coverage.json()["versions"][0]


def test_geography_registry_exposes_configured_scores() -> None:
    client = TestClient(create_app())

    response = client.get("/v1/geographies")

    assert response.status_code == 200
    payload = response.json()
    assert payload["fit_scores"]["country_specific"] == 100
    country_codes = {item["code"] for item in payload["items"] if item["level"] == "country"}
    assert len(country_codes) >= 249
    assert country_codes >= {"TR", "US", "DE", "JP", "ZA", "AU"}
    assert {item["code"] for item in payload["items"]} >= {"TR", "GLOBAL"}


class CountryRegistryRepositoryStub:
    async def list_countries(self, *, language: str = "en") -> list[dict[str, Any]]:
        names = {"en": "Denmark", "tr": "Danimarka"}
        return [
            {
                "code": "DK",
                "alpha3": "DNK",
                "numeric_code": "208",
                "name": names.get(language, "Denmark"),
                "canonical_name": "Denmark",
                "registry_version": "iso3166-test",
            }
        ]


def test_country_registry_exposes_iso_identity_and_requested_language() -> None:
    repository = CountryRegistryRepositoryStub()
    client = TestClient(create_app(repository=cast(Any, repository)))

    response = client.get("/v1/countries?language=tr")

    assert response.status_code == 200
    assert response.json() == {
        "registry_version": "iso3166-test",
        "language": "tr",
        "items": [
            {
                "code": "DK",
                "alpha3": "DNK",
                "numeric_code": "208",
                "name": "Danimarka",
                "canonical_name": "Denmark",
                "registry_version": "iso3166-test",
            }
        ],
    }


class GeographicRepositoryStub(FactorRepositoryStub):
    factor: ClassVar[dict[str, Any]] = {
        "factor_id": "atlas:ipcc:natural-gas",
        "name": "Natural Gas",
        "taxonomy_code": "atlas.energy.natural_gas",
        "activity_type": "fuel",
        "activity_unit": "m3",
        "factor_value": "2.0",
        "factor_unit": "kgCO2e/m3",
        "factor_value_kind": "co2e_total",
        "intended_use": "inventory",
        "source_health": "healthy",
        "data_quality": "source",
        "reference_year": 2026,
        "methodology": {
            "scope": "Scope 1",
            "system_boundary": "combustion",
            "methodology": "IPCC",
        },
        "origin_geography": {"level": "global", "code": "GLOBAL"},
        "applicable_geographies": [{"level": "global", "code": "GLOBAL"}],
        "geography_level": "global",
        "geographic_specificity": 0,
        "geographic_fit_type": "global",
    }

    async def coverage_candidates(self, **_: Any) -> list[dict[str, Any]]:
        return [self.factor]

    async def matching_candidates(self, **_: Any) -> list[dict[str, Any]]:
        return [self.factor]

    async def search_candidates(self, **_: Any) -> list[dict[str, Any]]:
        return [self.factor]

    async def recommendation_candidates(self, **_: Any) -> list[dict[str, Any]]:
        return [self.factor]

    async def get_published_factor(self, factor_id: str, **_: Any) -> dict[str, Any] | None:
        return self.factor if factor_id == self.factor["factor_id"] else None


class ConditionalNaturalGasRepositoryStub(GeographicRepositoryStub):
    factor: ClassVar[dict[str, Any]] = {
        **GeographicRepositoryStub.factor,
        "factor_id": "atlas:unfccc-tuik:natural-gas-energy",
        "source_code": "UNFCCC_TUIK",
        "concept_code": "energy.natural_gas",
        "activity_type": "energy",
        "activity_unit": "GJ",
        "factor_unit": "kgCO2e/GJ",
        "factor_value": "56.1",
        "methodology": {
            "scope": None,
            "system_boundary": "national_inventory_implied_factor",
            "methodology": "UNFCCC CRT_ETF source-derived curation",
        },
    }


class DieselRepositoryStub(GeographicRepositoryStub):
    factor: ClassVar[dict[str, Any]] = {
        **GeographicRepositoryStub.factor,
        "factor_id": "atlas:ghg-protocol:diesel-stationary-combustion",
        "source_code": "GHG_PROTOCOL",
        "name": "Gas/Diesel oil2 stationary combustion",
        "taxonomy_code": "atlas.energy.diesel.stationary_combustion",
        "concept_code": "energy.diesel",
        "activity_type": "fuel",
        "activity_unit": "tonne",
        "factor_unit": "kgCO2e/tonne",
        "factor_value": "3200",
        "methodology": {
            "scope": "Scope 1",
            "system_boundary": "stationary_combustion",
            "methodology": "GHG Protocol cross-sector tools",
            "details": {"original_source": "2006 IPCC Guidelines"},
        },
    }


class DomesticFlightRepositoryStub(GeographicRepositoryStub):
    factor: ClassVar[dict[str, Any]] = {
        **GeographicRepositoryStub.factor,
        "factor_id": "atlas:defra:flight-domestic-average-passenger",
        "source_code": "DEFRA",
        "name": "Business travel - air / Flights / Domestic, to/from UK / Average passenger",
        "taxonomy_code": "atlas.transport.air.domestic.passenger",
        "concept_code": None,
        "activity_type": "passenger-distance",
        "activity_unit": "passenger.km",
        "factor_unit": "kgCO2e/passenger.km",
        "factor_value": "0.2",
        "methodology": {
            "scope": "Scope 3",
            "system_boundary": "business_travel",
            "methodology": "DEFRA conversion factors",
        },
        "origin_geography": {"level": "country", "code": "GB"},
        "applicable_geographies": [{"level": "country", "code": "GB"}],
        "geography_level": "country",
        "geographic_specificity": 3,
        "geographic_fit_type": "country_specific",
    }


class SearchGeographyRepositoryStub(GeographicRepositoryStub):
    @staticmethod
    def _electricity(factor_id: str, geography: str, fit: str) -> dict[str, Any]:
        level = "global" if geography == "GLOBAL" else "country"
        return {
            **GeographicRepositoryStub.factor,
            "factor_id": factor_id,
            "name": "Grid Electricity",
            "taxonomy_code": "atlas.energy.electricity",
            "activity_type": "electricity",
            "activity_unit": "kWh",
            "factor_unit": "kgCO2e/kWh",
            "methodology": {"scope": "Scope 2"},
            "origin_geography": {"level": level, "code": geography},
            "applicable_geographies": [{"level": level, "code": geography}],
            "geography_level": level,
            "geographic_fit_type": fit,
        }

    async def search_candidates(self, **_: Any) -> list[dict[str, Any]]:
        return [
            self._electricity("electricity-de", "DE", "country_specific"),
            self._electricity("electricity-global", "GLOBAL", "global"),
            self._electricity("electricity-tr", "TR", "country_specific"),
        ]


class ExplorerElectricityRepositoryStub(SearchGeographyRepositoryStub):
    async def matching_candidates(self, **_: Any) -> list[dict[str, Any]]:
        return await self.search_candidates()


class IntelligenceRepositoryStub(FactorRepositoryStub):
    def __init__(self) -> None:
        super().__init__()
        self.target_languages: tuple[str, ...] = ()
        self.review_decision: dict[str, Any] = {}
        self.edited_translation: dict[str, Any] = {}

    async def intelligence_coverage(self, *, target_languages: tuple[str, ...]) -> dict[str, Any]:
        self.target_languages = target_languages
        return {
            "ready": False,
            "gates": {"approved_translation_coverage_complete": False},
        }

    async def translation_reviews(self, **filters: Any) -> list[dict[str, Any]]:
        self.filters = filters
        return [{"label_id": str(UUID(int=7)), "review_status": "draft"}]

    async def decide_translation_review(
        self,
        label_id: UUID,
        *,
        decision: str,
        reviewed_by: str,
        note: str | None,
    ) -> dict[str, Any]:
        if decision not in {"approved", "rejected"}:
            raise ValueError(f"unknown translation review decision: {decision}")
        self.review_decision = {
            "label_id": str(label_id),
            "decision": decision,
            "reviewed_by": reviewed_by,
            "review_note": note,
        }
        return self.review_decision

    async def edit_translation_draft(
        self,
        label_id: UUID,
        *,
        label: str,
        definition: str | None,
    ) -> dict[str, Any]:
        self.edited_translation = {
            "label_id": str(label_id),
            "label": label,
            "definition": definition,
            "review_status": "draft",
        }
        return self.edited_translation

    async def translation_jobs(self, *, limit: int = 100) -> list[dict[str, Any]]:
        self.filters = {"limit": limit}
        return [{"job_id": str(UUID(int=9)), "status": "completed"}]

    async def list_glossary(self, *, target_language: str | None) -> list[dict[str, Any]]:
        self.filters = {"target_language": target_language}
        return [
            {
                "source_term": "CO2e",
                "target_language": target_language,
                "target_term": None,
                "protected": True,
            }
        ]


class ChunkedTranslationRepositoryStub(IntelligenceRepositoryStub):
    def __init__(self, count: int) -> None:
        super().__init__()
        self.inputs = [
            SimpleNamespace(
                concept_code=f"concept.{index:03d}",
                canonical_name_en=f"Concept {index:03d}",
            )
            for index in range(count)
        ]
        self.created_jobs: list[dict[str, Any]] = []

    async def translation_inputs(self, **_: Any) -> list[Any]:
        return self.inputs

    async def glossary_terms(self, **_: Any) -> tuple[str, ...]:
        return ("PRESERVE: CO2e",)

    async def glossary_version(self, **_: Any) -> str:
        return "sha256:test"

    async def create_translation_job(self, **payload: Any) -> dict[str, Any]:
        job = {
            "job_id": str(uuid4()),
            "requested_count": len(payload["custom_ids"]),
            "status": "submitted",
            **payload,
        }
        self.created_jobs.append(job)
        return job

    async def ingest_translation_results(
        self, job_id: UUID, results: dict[str, TranslationDraft]
    ) -> dict[str, int]:
        job = next(job for job in self.created_jobs if job["job_id"] == str(job_id))
        job["status"] = "review_required"
        job["completed_count"] = len(results)
        return {"draft_terms_generated": len(results), "qa_flagged": 0}

    async def get_translation_job(self, job_id: UUID) -> dict[str, Any] | None:
        return next((job for job in self.created_jobs if job["job_id"] == str(job_id)), None)


class FakeOpenAITranslationProvider:
    prompt_version = "test-prompt"
    submissions: ClassVar[list[int]] = []

    def __init__(self, **_: Any) -> None:
        self.translation_model = "test-translation-model"
        self.qa_model = "test-qa-model"

    def submit_batch(self, items: list[Any], **_: Any) -> SimpleNamespace:
        self.submissions.append(len(items))
        ordinal = len(self.submissions)
        return SimpleNamespace(
            provider_job_id=f"batch-{ordinal}",
            input_file_id=f"file-{ordinal}",
            custom_ids={
                f"concept-{index:06d}": item.concept_code
                for index, item in enumerate(items, start=1)
            },
        )

    def generate_group(self, items: list[Any], **_: Any) -> SimpleNamespace:
        self.submissions.append(len(items))
        ordinal = len(self.submissions)
        custom_ids = {
            f"concept-{index:06d}": item.concept_code for index, item in enumerate(items, start=1)
        }
        return SimpleNamespace(
            provider_job_id=f"response-{ordinal}",
            custom_ids=custom_ids,
            results={
                custom_id: TranslationDraft(
                    preferred_term=concept_code,
                    definition=f"Definition of {concept_code}",
                )
                for custom_id, concept_code in custom_ids.items()
            },
        )


def test_intelligence_coverage_uses_all_registry_target_languages() -> None:
    repository = IntelligenceRepositoryStub()
    client = TestClient(create_app(repository=cast(Any, repository)))

    response = client.get(
        "/v1/admin/intelligence/coverage",
        headers={"X-Atlas-Admin-Key": "replace-this-local-admin-key"},
    )

    assert response.status_code == 200
    assert response.json()["ready"] is False
    assert repository.target_languages == ("en", "tr", "de", "fr", "es", "ru", "ar")


def test_translation_review_endpoints_filter_and_audit_decisions() -> None:
    repository = IntelligenceRepositoryStub()
    client = TestClient(create_app(repository=cast(Any, repository)))
    headers = {"X-Atlas-Admin-Key": "replace-this-local-admin-key"}

    listed = client.get(
        "/v1/admin/translations?review_status=draft&language=tr&limit=25&offset=5",
        headers=headers,
    )
    decided = client.post(
        f"/v1/admin/translations/{UUID(int=7)}/approved",
        headers=headers,
        json={"decided_by": "language-reviewer", "note": "Terminology verified"},
    )

    assert listed.status_code == 200
    assert listed.json()["items"][0]["review_status"] == "draft"
    assert repository.filters == {
        "review_status": "draft",
        "language": "tr",
        "limit": 25,
        "offset": 5,
    }
    assert decided.status_code == 200
    assert repository.review_decision == {
        "label_id": str(UUID(int=7)),
        "decision": "approved",
        "reviewed_by": "language-reviewer",
        "review_note": "Terminology verified",
    }


def test_translation_admin_lists_jobs_glossary_and_edits_drafts() -> None:
    repository = IntelligenceRepositoryStub()
    client = TestClient(create_app(repository=cast(Any, repository)))
    headers = {"X-Atlas-Admin-Key": "replace-this-local-admin-key"}

    jobs = client.get("/v1/admin/translation-jobs?limit=12", headers=headers)
    glossary = client.get(
        "/v1/admin/translation-glossary?language=tr",
        headers=headers,
    )
    edited = client.patch(
        f"/v1/admin/translations/{UUID(int=7)}",
        headers=headers,
        json={"label": "Doğal gaz", "definition": "Enerji girdisi olan gaz."},
    )

    assert jobs.status_code == 200
    assert jobs.json()["items"][0]["status"] == "completed"
    assert glossary.status_code == 200
    assert glossary.json()["items"][0]["protected"] is True
    assert edited.status_code == 200
    assert repository.edited_translation == {
        "label_id": str(UUID(int=7)),
        "label": "Doğal gaz",
        "definition": "Enerji girdisi olan gaz.",
        "review_status": "draft",
    }


def test_translation_submission_splits_work_into_fifty_item_batches(
    monkeypatch: Any,
) -> None:
    repository = ChunkedTranslationRepositoryStub(121)
    FakeOpenAITranslationProvider.submissions = []
    monkeypatch.setattr(
        "atlas.api.app.OpenAITranslationProvider",
        FakeOpenAITranslationProvider,
    )
    settings = Settings(_env_file=None, openai_api_key="test-key")
    client = TestClient(create_app(repository=cast(Any, repository), settings=settings))

    response = client.post(
        "/v1/admin/translation-jobs",
        headers={"X-Atlas-Admin-Key": "replace-this-local-admin-key"},
        json={
            "target_language": "en",
            "requested_by": "test-reviewer",
            "only_missing": True,
            "batch_size": 50,
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "submitted"
    assert response.json()["batch_count"] == 3
    assert response.json()["requested_count"] == 121
    assert response.json()["remaining_count"] == 0
    assert FakeOpenAITranslationProvider.submissions == [50, 50, 21]
    assert [job["requested_count"] for job in repository.created_jobs] == [50, 50, 21]


def test_translation_batch_size_cannot_exceed_fifty() -> None:
    client = TestClient(create_app(repository=cast(Any, IntelligenceRepositoryStub())))

    response = client.post(
        "/v1/admin/translation-jobs",
        headers={"X-Atlas-Admin-Key": "replace-this-local-admin-key"},
        json={
            "target_language": "en",
            "requested_by": "test-reviewer",
            "batch_size": 51,
        },
    )

    assert response.status_code == 422


def test_translation_responses_mode_completes_fifty_item_groups(
    monkeypatch: Any,
) -> None:
    repository = ChunkedTranslationRepositoryStub(51)
    FakeOpenAITranslationProvider.submissions = []
    monkeypatch.setattr(
        "atlas.api.app.OpenAITranslationProvider",
        FakeOpenAITranslationProvider,
    )
    settings = Settings(_env_file=None, openai_api_key="test-key")
    client = TestClient(create_app(repository=cast(Any, repository), settings=settings))

    response = client.post(
        "/v1/admin/translation-jobs",
        headers={"X-Atlas-Admin-Key": "replace-this-local-admin-key"},
        json={
            "target_language": "en",
            "requested_by": "test-reviewer",
            "only_missing": True,
            "batch_size": 50,
            "execution_mode": "responses",
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "completed"
    assert response.json()["execution_mode"] == "responses"
    assert response.json()["batch_count"] == 2
    assert response.json()["requested_count"] == 51
    assert FakeOpenAITranslationProvider.submissions == [50, 1]
    assert all(job["status"] == "review_required" for job in repository.created_jobs)


def test_translation_review_rejects_unknown_decision() -> None:
    client = TestClient(create_app(repository=cast(Any, IntelligenceRepositoryStub())))

    response = client.post(
        f"/v1/admin/translations/{UUID(int=7)}/publish",
        headers={"X-Atlas-Admin-Key": "replace-this-local-admin-key"},
        json={"decided_by": "language-reviewer"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "unknown translation review decision: publish"


def test_country_coverage_counts_global_applicable_factor() -> None:
    client = TestClient(create_app(repository=cast(Any, GeographicRepositoryStub())))

    response = client.get("/v1/geographies/TR/coverage")

    assert response.status_code == 200
    assert response.json()["coverage"]["global"] == 1
    assert response.json()["total_available"] == 1


def test_recommendation_returns_explicit_geographic_fallback_notice() -> None:
    client = TestClient(create_app(repository=cast(Any, GeographicRepositoryStub())))

    response = client.post(
        "/v1/recommendations",
        json={
            "mode": "suggest",
            "context": "corporate_carbon",
            "year": 2026,
            "calculation_profile": "corporate_carbon.ghg_protocol.scope1",
            "facility_context": {"country": "TR"},
            "activity": {"text": "natural gas", "quantity": 10, "unit": "m3"},
        },
    )

    assert response.status_code == 200
    selected = response.json()["recommended"]
    assert selected["factor"]["factor_id"] == "atlas:ipcc:natural-gas"
    assert selected["geography"] == {
        "requested_geography": "TR",
        "factor_geography": "GLOBAL",
        "geographic_fit": "global",
        "geographic_score": 50,
        "fallback_rank": 5,
        "exact_geography": False,
        "fallback_used": True,
        "eligible": True,
        "warning": "No exact TR geography was selected; using GLOBAL with global fit",
    }


def test_unit_conversion_api_reverses_factor_denominator_direction() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/convert",
        json={
            "mode": "factor",
            "value": "0.5",
            "from_unit": "kgCO2e/kWh",
            "to_unit": "kgCO2e/MWh",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "exact_conversion"
    assert Decimal(response.json()["output_value"]) == Decimal("500")


def test_explorer_calculate_uses_selected_factor_on_server() -> None:
    client = TestClient(create_app(repository=cast(Any, GeographicRepositoryStub())))

    response = client.post(
        "/v1/explorer/calculate",
        json={
            "factor_id": "atlas:ipcc:natural-gas",
            "quantity": "10",
            "unit": "m3",
            "country": "TR",
            "context": "corporate_carbon",
            "calculation_profile": "corporate_carbon.ghg_protocol.scope1",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "calculated"
    assert response.json()["result"] == {"value": "20.0", "unit": "kgCO2e"}


def test_explorer_calculate_requests_parameter_after_selecting_convertible_factor() -> None:
    client = TestClient(create_app(repository=cast(Any, ConditionalNaturalGasRepositoryStub())))

    response = client.post(
        "/v1/explorer/calculate",
        json={
            "factor_id": "atlas:unfccc-tuik:natural-gas-energy",
            "quantity": "100",
            "unit": "m3",
            "country": "TR",
            "context": "corporate_carbon",
            "calculation_profile": "corporate_carbon.ghg_protocol.scope1",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "conversion_parameter_required"
    assert response.json()["required_parameters"] == ["calorific_value"]
    assert response.json()["decision"]["eligibility"]["calculation_eligible"] is True


def test_scope1_diesel_search_returns_ipcc_derived_total_for_mass_input() -> None:
    client = TestClient(create_app(repository=cast(Any, DieselRepositoryStub())))

    response = client.post(
        "/v1/search",
        json={
            "query": "diesel",
            "context": "corporate_carbon",
            "calculation_profile": "corporate_carbon.ghg_protocol.scope1",
            "geography": "TR",
            "year": 2025,
            "unit": "kg",
        },
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["factor"]["source_code"] == "GHG_PROTOCOL"
    assert item["factor"]["methodology"]["details"]["original_source"] == ("2006 IPCC Guidelines")
    assert item["concept_codes"] == ["energy.diesel"]
    assert item["eligibility"]["calculation_eligible"] is True
    assert item["unit_conversion_status"] == "exact_conversion"


def test_unit_registry_exposes_all_groupable_activity_options_at_once() -> None:
    client = TestClient(create_app())

    response = client.get("/v1/units")

    assert response.status_code == 200
    units = {item["code"]: item for item in response.json()["items"]}
    assert units["kWh"]["dimension"] == "energy"
    assert units["kg"]["dimension"] == "mass"
    assert units["m3"]["dimension"] == "volume"
    assert units["passenger"]["dimension"] == "passenger_count"
    assert units["passenger.km"]["dimension"] == "passenger_distance"


def test_scope3_domestic_passenger_search_then_requires_distance_to_calculate() -> None:
    client = TestClient(create_app(repository=cast(Any, DomesticFlightRepositoryStub())))
    payload = {
        "query": "domestic",
        "context": "corporate_carbon",
        "calculation_profile": "corporate_carbon.ghg_protocol.scope3",
        "geography": "GB",
        "year": 2025,
        "unit": "passenger",
    }

    searched = client.post("/v1/search", json=payload)
    missing = client.post(
        "/v1/explorer/calculate",
        json={
            "factor_id": "atlas:defra:flight-domestic-average-passenger",
            "quantity": "2",
            "unit": "passenger",
            "country": "GB",
            "context": "corporate_carbon",
            "calculation_profile": "corporate_carbon.ghg_protocol.scope3",
            "year": 2025,
        },
    )
    calculated = client.post(
        "/v1/explorer/calculate",
        json={
            "factor_id": "atlas:defra:flight-domestic-average-passenger",
            "quantity": "2",
            "unit": "passenger",
            "country": "GB",
            "context": "corporate_carbon",
            "calculation_profile": "corporate_carbon.ghg_protocol.scope3",
            "year": 2025,
            "conversion_parameters": [
                {"name": "distance", "value": "500", "unit": "km", "source": "itinerary"}
            ],
        },
    )

    assert searched.status_code == 200
    assert searched.json()["items"][0]["unit_conversion_status"] == "conditional_conversion"
    assert missing.status_code == 200
    assert missing.json()["status"] == "conversion_parameter_required"
    assert missing.json()["required_parameters"] == ["distance"]
    assert calculated.status_code == 200
    assert calculated.json()["activity"]["normalized_value"] == "1000"
    assert calculated.json()["activity"]["normalized_unit"] == "passenger.km"
    assert calculated.json()["result"] == {"value": "200.0", "unit": "kgCO2e"}


def test_search_filters_foreign_country_and_ranks_exact_before_global() -> None:
    client = TestClient(create_app(repository=cast(Any, SearchGeographyRepositoryStub())))

    response = client.post(
        "/v1/search",
        json={
            "query": "Elektrik",
            "context": "corporate_carbon",
            "calculation_profile": "corporate_carbon.ghg_protocol.scope2_location",
            "geography": "TR",
        },
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["factor"]["factor_id"] for item in items] == [
        "electricity-tr",
        "electricity-global",
    ]
    assert items[0]["geographic_coverage"]["exact_geography"] is True
    assert items[1]["geographic_coverage"]["fallback_used"] is True


def test_search_extracts_country_name_when_structured_geography_is_missing() -> None:
    class QueryGeographyRepositoryStub(GeographicRepositoryStub):
        def __init__(self) -> None:
            super().__init__()
            self.search_filters: dict[str, Any] = {}

        async def search_candidates(self, **filters: Any) -> list[dict[str, Any]]:
            self.search_filters = filters
            return []

    repository = QueryGeographyRepositoryStub()
    client = TestClient(create_app(repository=cast(Any, repository)))

    response = client.post(
        "/v1/search",
        json={
            "query": "banana Denmark",
            "context": "lca",
            "calculation_profile": "lca.iso14040",
        },
    )

    assert response.status_code == 200
    assert response.json()["query"] == "banana Denmark"
    assert repository.search_filters["query"] == "banana"
    assert repository.search_filters["geography_codes"][:2] == ("DK", "EUROPE")


def test_compare_context_preserves_selected_profile_for_current_context() -> None:
    client = TestClient(create_app(repository=cast(Any, ExplorerElectricityRepositoryStub())))

    response = client.post(
        "/v1/explorer/compare",
        json={
            "mode": "context",
            "activity": "Elektrik",
            "quantity": 100,
            "unit": "kWh",
            "country": "TR",
            "context": "corporate_carbon",
            "calculation_profile": "corporate_carbon.ghg_protocol.scope2_location",
            "year": 2025,
        },
    )

    assert response.status_code == 200
    corporate = response.json()["items"][0]
    assert corporate["status"] == "calculated"
    assert corporate["calculation_profile"] == ("corporate_carbon.ghg_protocol.scope2_location")
    assert corporate["selected"]["geographic_coverage"]["factor_geography"] == "TR"


def test_recommendation_rejects_profile_from_another_context() -> None:
    client = TestClient(create_app(repository=cast(Any, GeographicRepositoryStub())))

    response = client.post(
        "/v1/recommendations",
        json={
            "mode": "suggest",
            "context": "pcf",
            "calculation_profile": "corporate_carbon.ghg_protocol.scope1",
            "facility_context": {"country": "TR"},
            "activity": {"text": "natural gas", "quantity": 10, "unit": "m3"},
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "calculation profile does not belong to requested context"


def test_context_registry_exposes_versioned_profiles() -> None:
    client = TestClient(create_app())

    response = client.get("/v1/contexts/cbam/profiles")

    assert response.status_code == 200
    assert response.json()["items"][0]["code"] == "cbam.eu_definitive"


def test_scope3_category_contract_exposes_all_ghg_protocol_categories() -> None:
    client = TestClient(create_app())

    response = client.get("/v1/scope3/categories")
    rules = client.get("/v1/profiles/corporate_carbon.ghg_protocol.scope3/rules")

    assert response.status_code == 200
    categories = response.json()["items"]
    assert [item["code"] for item in categories] == list(range(1, 16))
    assert categories[0]["supported_families"] == ["purchased_services"]
    assert categories[3]["supported_families"] == ["road_freight"]
    assert categories[8]["supported_families"] == ["road_freight"]
    assert categories[14]["availability"] == "not_supported"
    assert rules.status_code == 200
    assert rules.json()["scope3_categories"] == categories


def test_turkish_search_uses_concept_registry_and_context_policy() -> None:
    client = TestClient(create_app(repository=cast(Any, GeographicRepositoryStub())))

    response = client.post(
        "/v1/search",
        json={
            "query": "doğalgaz",
            "context": "corporate_carbon",
            "language": "tr",
            "unit": "m3",
        },
    )

    assert response.status_code == 200
    assert response.json()["calculation_profile"] == "corporate_carbon.ghg_protocol.scope1"
    assert response.json()["items"][0]["eligibility"]["calculation_eligible"] is True
    assert response.json()["items"][0]["concept_codes"] == ["energy.natural_gas"]


def test_removed_match_and_resolve_routes_are_absent_from_openapi() -> None:
    client = TestClient(create_app(repository=cast(Any, GeographicRepositoryStub())))
    paths = client.get("/openapi.json").json()["paths"]

    assert "/v1/match" not in paths
    assert "/v1/resolve" not in paths
    assert "/v1/recommendations" in paths


def test_cbam_search_hides_hard_denied_inventory_factors_including_debug() -> None:
    client = TestClient(create_app(repository=cast(Any, GeographicRepositoryStub())))
    payload = {
        "query": "Electricity",
        "context": "cbam",
        "calculation_profile": "cbam.eu_definitive",
        "geography": "TR",
    }

    response = client.post("/v1/search", json=payload)
    debug_response = client.post("/v1/search", json={**payload, "include_ineligible": True})

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert debug_response.status_code == 200
    assert debug_response.json()["items"] == []


def test_search_suggests_gj_factor_for_m3_when_parameter_is_required() -> None:
    client = TestClient(create_app(repository=cast(Any, ConditionalNaturalGasRepositoryStub())))

    response = client.post(
        "/v1/search",
        json={
            "query": "Natural gas",
            "context": "corporate_carbon",
            "calculation_profile": "corporate_carbon.ghg_protocol.scope1",
            "geography": "TR",
            "year": 2025,
            "unit": "m3",
        },
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["factor"]["factor_id"] == "atlas:unfccc-tuik:natural-gas-energy"
    assert item["eligibility"]["calculation_eligible"] is True
    assert item["unit_conversion_status"] == "conditional_conversion"
    assert "unit_parameter_required" in item["reason_codes"]


def test_natural_gas_search_rejects_electricity_generation_activity() -> None:
    class NaturalGasSearchRepository(GeographicRepositoryStub):
        async def search_candidates(self, **_: Any) -> list[dict[str, Any]]:
            combustion = {
                **self.factor,
                "factor_id": "gas-combustion",
                "source_code": "IPCC",
                "concept_code": "energy.natural_gas",
                "activity_unit": "GJ",
                "factor_unit": "kgCO2e/GJ",
            }
            generation = {
                **combustion,
                "factor_id": "gas-electricity",
                "source_code": "ETKB",
                "name": "Electricity generation - Natural gas - CO2e",
                "taxonomy_code": "atlas.energy.electricity.fuel_generation",
                "concept_code": "energy.natural_gas",
                "methodology": {"scope": "Scope 1"},
            }
            return [generation, combustion]

    client = TestClient(create_app(repository=cast(Any, NaturalGasSearchRepository())))

    response = client.post(
        "/v1/search",
        json={
            "query": "Natural gas",
            "context": "corporate_carbon",
            "calculation_profile": "corporate_carbon.ghg_protocol.scope1",
            "geography": "TR",
            "include_ineligible": True,
        },
    )

    assert response.status_code == 200
    assert [item["factor"]["factor_id"] for item in response.json()["items"]] == ["gas-combustion"]


def test_natural_gas_search_rejects_products_made_from_natural_gas() -> None:
    class DerivedProductRepository(GeographicRepositoryStub):
        async def search_candidates(self, **_: Any) -> list[dict[str, Any]]:
            derived = {
                **self.factor,
                "factor_id": "ammonia-from-gas",
                "name": "Ammonia - WTW fuel emission factor (From Natural gas)",
                "concept_code": "energy.natural_gas",
                "taxonomy_code": "atlas.transport.energy_carrier",
                "activity_type": "transport-energy",
                "methodology": {"scope": None, "details": {"application": "From Natural gas"}},
            }
            return [derived, self.factor]

    client = TestClient(create_app(repository=cast(Any, DerivedProductRepository())))

    response = client.post(
        "/v1/search",
        json={
            "query": "Natural gas",
            "context": "corporate_carbon",
            "calculation_profile": "corporate_carbon.ghg_protocol.scope1",
            "geography": "TR",
            "include_ineligible": True,
        },
    )

    assert response.status_code == 200
    assert [item["factor"]["factor_id"] for item in response.json()["items"]] == [
        "atlas:ipcc:natural-gas"
    ]
