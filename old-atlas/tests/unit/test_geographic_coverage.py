from __future__ import annotations

from pathlib import Path

from atlas.geography import GeographicCoverageEngine
from atlas.matching import FactorMatchingEngine, MatchRequest


def _factor(
    factor_id: str,
    *,
    fit: str,
    level: str,
    geography: str,
    year: int = 2026,
) -> dict[str, object]:
    return {
        "factor_id": factor_id,
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
        "reference_year": year,
        "methodology": {
            "scope": "Scope 1",
            "system_boundary": "combustion",
            "methodology": "IPCC",
        },
        "origin_geography": {"level": level, "code": geography},
        "applicable_geographies": [{"level": level, "code": geography}],
        "geography_level": level,
        "geographic_specificity": {"global": 0, "continent": 1, "country": 3}[level],
        "geographic_fit_type": fit,
    }


def test_global_factor_is_explicit_fallback_for_turkiye() -> None:
    engine = GeographicCoverageEngine()
    evaluation = engine.evaluate(
        "TR", _factor("global", fit="global", level="global", geography="GLOBAL")
    )

    assert evaluation.eligible is True
    assert evaluation.factor_geography == "GLOBAL"
    assert evaluation.geographic_score == 50
    assert evaluation.fallback_used is True
    assert evaluation.warning is not None


def test_egrid_hierarchy_resolves_grid_to_country_and_global() -> None:
    engine = GeographicCoverageEngine()

    assert engine.ancestors("MROW") == ("US", "NORTH_AMERICA", "GLOBAL")


def test_country_names_and_curated_aliases_resolve_to_iso_code() -> None:
    engine = GeographicCoverageEngine()

    assert engine.resolve_code("Denmark") == "DK"
    assert engine.resolve_code("Danimarka") == "DK"
    assert engine.resolve_code("Danmark") == "DK"


def test_query_country_is_extracted_without_guessing_ambiguous_codes() -> None:
    engine = GeographicCoverageEngine()

    english = engine.extract_query_geography("banana Denmark")
    code = engine.extract_query_geography("banana dk")

    assert english is not None
    assert english.geography_code == "DK"
    assert english.search_query == "banana"
    assert code is not None
    assert code.geography_code == "DK"
    assert engine.extract_query_geography("rice in packaging") is None


def test_matching_prefers_exact_country_over_higher_non_geographic_dimensions() -> None:
    geography = GeographicCoverageEngine()
    matching = FactorMatchingEngine(geography)
    request = MatchRequest(
        activity="natural gas",
        country="TR",
        year=2026,
        calculation_profile="corporate_carbon.ghg_protocol.scope1",
    )
    global_factor = _factor("global", fit="global", level="global", geography="GLOBAL", year=2026)
    country_factor = _factor(
        "tr-specific", fit="country_specific", level="country", geography="TR", year=2020
    )

    response = matching.match(request, [global_factor, country_factor])

    assert response.selected.factor["factor_id"] == "tr-specific"
    assert response.selected.geographic_coverage.fallback_used is False
    assert response.alternatives[0].factor["factor_id"] == "global"


def test_matching_can_use_foreign_factor_only_as_explicit_opt_in_proxy() -> None:
    matching = FactorMatchingEngine(GeographicCoverageEngine())
    request = MatchRequest(
        activity="Buğday",
        country="TR",
        calculation_profile="pcf.iso14067",
        activity_unit="kg",
        allow_geographic_proxy=True,
    )
    factor = _factor("fr-wheat", fit="country_modelled", level="country", geography="FR")
    factor.update(
        {
            "name": "Blé tendre, à la ferme, France",
            "taxonomy_code": "agriculture.wheat",
            "activity_unit": "kg",
            "factor_unit": "kgCO2e/kg",
            "entity_type": "lca_result",
            "intended_use": "characterization",
            "methodology": {},
        }
    )

    response = matching.match(request, [factor])

    assert response.selected.factor["factor_id"] == "fr-wheat"
    assert response.selected.score.activity == 100
    assert response.selected.geographic_coverage.fallback_used is True
    assert "explicit geographic proxy" in response.selected.geographic_coverage.warning


def test_natural_gas_does_not_select_electricity_generation_factor() -> None:
    matching = FactorMatchingEngine(GeographicCoverageEngine())
    request = MatchRequest(
        activity="Natural gas",
        country="TR",
        calculation_profile="corporate_carbon.ghg_protocol.scope1",
        activity_unit="kWh",
    )
    electricity = _factor(
        "gas-electricity", fit="country_specific", level="country", geography="TR"
    )
    electricity.update(
        {
            "name": "Elektrik Üretimi — Doğalgaz — CO2e",
            "taxonomy_code": "atlas.energy.electricity.fuel_generation",
            "activity_unit": "kWh",
            "factor_unit": "kgCO2e/kWh",
        }
    )
    combustion = _factor("gas-combustion", fit="global", level="global", geography="GLOBAL")
    combustion.update({"activity_unit": "kWh", "factor_unit": "kgCO2e/kWh"})

    response = matching.match(request, [electricity, combustion])

    assert response.selected.factor["factor_id"] == "gas-combustion"
    assert response.rejected == ()


def test_matching_keeps_parameterized_conversion_candidate_selectable() -> None:
    matching = FactorMatchingEngine(GeographicCoverageEngine())
    request = MatchRequest(
        activity="Natural gas",
        country="TR",
        calculation_profile="corporate_carbon.ghg_protocol.scope1",
        quantity=100,
        activity_unit="m3",
    )
    factor = _factor("gas-energy", fit="country_specific", level="country", geography="TR")
    factor.update(
        {
            "concept_code": "energy.natural_gas",
            "activity_unit": "GJ",
            "factor_unit": "kgCO2e/GJ",
        }
    )

    response = matching.match(request, [factor])

    assert response.selected.factor["factor_id"] == "gas-energy"
    assert response.selected.eligibility.calculation_eligible is True
    assert response.selected.unit_conversion_status == "conditional_conversion"
    assert "unit_parameter_required" in response.selected.warnings


def test_turkiye_official_electricity_reaches_full_scope2_match() -> None:
    matching = FactorMatchingEngine(GeographicCoverageEngine())
    request = MatchRequest(
        activity="Elektrik",
        country="TR",
        year=2025,
        calculation_profile="corporate_carbon.ghg_protocol.scope2_location",
        activity_unit="kWh",
    )
    factor = _factor(
        "etkb-distribution", fit="country_specific", level="country", geography="TR", year=2021
    )
    factor.update(
        {
            "source_code": "ETKB",
            "name": "Distribution-connected consumption point - CO2e",
            "taxonomy_code": "atlas.energy.electricity.grid_mix",
            "activity_type": "purchased-electricity",
            "activity_unit": "kWh",
            "factor_unit": "kgCO2e/kWh",
            "data_quality": "ETKB official annual default",
            "methodology": {"scope": "scope_2"},
        }
    )

    response = matching.match(request, [factor])

    assert response.selected.score.activity == 100
    assert response.selected.score.year == 100
    assert response.selected.score.data_quality == 100
    assert response.selected.score.final == 100


def test_ipcc_primary_factor_stays_visible_with_ipcc_derived_ghg_factor() -> None:
    matching = FactorMatchingEngine(GeographicCoverageEngine())
    request = MatchRequest(
        activity="Natural gas",
        country="TR",
        calculation_profile="corporate_carbon.ghg_protocol.scope1",
        activity_unit="GJ",
    )
    factors = []
    for index in range(4):
        factor = _factor(f"ghg-{index}", fit="global", level="global", geography="GLOBAL")
        factor.update(
            {
                "source_code": "GHG_PROTOCOL",
                "activity_unit": "GJ",
                "factor_unit": "kgCO2e/GJ",
                "methodology": {
                    "scope": "scope_1",
                    "details": {"original_source": "2006 IPCC Guidelines"},
                },
            }
        )
        factors.append(factor)
    primary = _factor("ipcc-primary", fit="global", level="global", geography="GLOBAL")
    primary.update(
        {
            "source_code": "IPCC",
            "activity_unit": "GJ",
            "factor_unit": "kgCO2e/GJ",
        }
    )
    factors.append(primary)

    response = matching.match(request, factors)

    assert "IPCC" in {
        item.factor.get("source_code") for item in (response.selected, *response.alternatives)
    }


def test_fit_scores_are_loaded_from_atlas_configuration(tmp_path: Path) -> None:
    config = tmp_path / "geography.yaml"
    config.write_text(
        """
version: test
fit_scores:
  country_specific: 99
  country_modelled: 88
  regional: 77
  continental: 66
  global: 44
  proxy: 12
fallback_order:
  - country_specific
  - country_modelled
  - regional
  - continental
  - global
  - proxy
geographies:
  GLOBAL: {level: global, name: Global, parent: null}
  TR: {level: country, name: Türkiye, parent: GLOBAL}
proxy_rules: {}
""".strip(),
        encoding="utf-8",
    )
    engine = GeographicCoverageEngine(config)

    evaluation = engine.evaluate(
        "TR", _factor("global", fit="global", level="global", geography="GLOBAL")
    )

    assert evaluation.geographic_score == 44
