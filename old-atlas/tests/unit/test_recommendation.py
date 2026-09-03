# ruff: noqa: RUF001
from __future__ import annotations

from typing import Any

import pytest

from atlas.recommendation import RecommendationEngine, RecommendationRequest


def factor(
    factor_id: str,
    *,
    name: str,
    source: str,
    geography: str = "GLOBAL",
    fit: str = "global",
    activity_unit: str = "GJ",
    factor_unit: str = "kgCO2e/GJ",
    scope: str = "Scope 1",
    taxonomy: str = "atlas.energy",
    activity_type: str = "energy",
    year: int | None = 2024,
) -> dict[str, Any]:
    level = "global" if geography == "GLOBAL" else "country"
    return {
        "factor_id": factor_id,
        "factor_version_id": f"version-{factor_id}",
        "name": name,
        "source_code": source,
        "source_health": "healthy",
        "taxonomy_code": taxonomy,
        "concept_code": taxonomy.removeprefix("atlas."),
        "activity_type": activity_type,
        "activity_unit": activity_unit,
        "factor_value": "56.1",
        "factor_unit": factor_unit,
        "entity_type": "emission_factor",
        "factor_value_kind": "co2e_total",
        "intended_use": "inventory",
        "reference_year": year,
        "methodology": {"scope": scope, "system_boundary": "combustion"},
        "origin_geography": {"level": level, "code": geography},
        "applicable_geographies": [{"level": level, "code": geography}],
        "geography_level": level,
        "geographic_specificity": 0 if level == "global" else 3,
        "geographic_fit_type": fit,
    }


def request(
    text: str,
    *,
    country: str = "TR",
    unit: str = "GJ",
    profile: str = "corporate_carbon.ghg_protocol.scope1",
    mode: str = "suggest",
    accept_proxy: bool = False,
    qualifiers: dict[str, str] | None = None,
    scope3_category: int | None = None,
) -> RecommendationRequest:
    return RecommendationRequest.model_validate(
        {
            "mode": mode,
            "context": "corporate_carbon",
            "calculation_profile": profile,
            "year": 2025,
            "facility_context": {"country": country},
            "activity": {
                "text": text,
                "quantity": "100",
                "unit": unit,
                "qualifiers": qualifiers or {},
                "scope3_category": scope3_category,
            },
            "accept_proxy": accept_proxy,
        }
    )


def test_tr_natural_gas_uses_global_before_foreign_country_proxy() -> None:
    engine = RecommendationEngine()
    global_ghg = factor("ghg-ng", name="Natural gas combustion", source="GHG_PROTOCOL")
    foreign_defra = factor(
        "defra-ng",
        name="Natural gas combustion",
        source="DEFRA",
        geography="GB",
        fit="country_specific",
    )

    response = engine.recommend(request("doğalgaz"), [foreign_defra, global_ghg])

    assert response.status == "recommended"
    assert response.recommended is not None
    assert response.recommended.factor["factor_id"] == "ghg-ng"
    assert response.recommended.rank.tier == "global"


def test_natural_gas_does_not_select_products_derived_from_natural_gas() -> None:
    engine = RecommendationEngine()
    direct = factor("ghg-ng", name="Natural gas4 stationary combustion", source="GHG_PROTOCOL")
    liquids = factor(
        "ghg-ngl", name="Natural Gas Liquids stationary combustion", source="GHG_PROTOCOL"
    )
    hydrogen = factor(
        "glec-h2",
        name="Hydrogen - WTW fuel emission factor (From Natural gas)",
        source="GLEC",
        activity_unit="MJ",
        factor_unit="kgCO2e/MJ",
        activity_type="transport-energy",
    )

    response = engine.recommend(request("natural gas"), [liquids, hydrogen, direct])

    assert response.recommended is not None
    assert response.recommended.factor["factor_id"] == "ghg-ng"


def test_diesel_does_not_select_biodiesel_or_transport_wtw_carriers() -> None:
    direct = factor(
        "ghg-diesel", name="Gas/Diesel oil stationary combustion", source="GHG_PROTOCOL"
    )
    biodiesel = factor(
        "epa-b100",
        name="Biodiesel (100%)",
        source="EPA",
        geography="US",
        fit="country_specific",
    )

    response = RecommendationEngine().recommend(
        request("diesel", country="US"), [biodiesel, direct]
    )

    assert response.recommended is not None
    assert response.recommended.factor["factor_id"] == "ghg-diesel"


def test_diesel_projection_does_not_classify_unrelated_oil_or_gas_factors() -> None:
    policy = RecommendationEngine().policy

    assert policy.classify_factor(
        factor("epa-asphalt", name="Asphalt and Road Oil", source="EPA")
    ) is None
    assert policy.classify_factor(
        factor("epa-furnace", name="Blast Furnace Gas", source="EPA")
    ) is None
    assert policy.classify_factor(
        factor("epa-heavy-oil", name="Heavy Gas Oils", source="EPA")
    ) is None


def test_gasoline_litre_selects_stationary_motor_gasoline_factor() -> None:
    response = RecommendationEngine().recommend(
        request("benzin", unit="l"),
        [
            factor(
                "ghg-gasoline-litre",
                name="Motor gasoline2 stationary combustion",
                source="GHG_PROTOCOL",
                activity_unit="l",
                factor_unit="kgCO2e/l",
                year=None,
            )
        ],
    )

    assert response.status == "recommended"
    assert response.intent.concept_code == "energy.gasoline"
    assert response.intent.family_code == "gasoline"
    assert response.recommended is not None
    assert response.recommended.factor["factor_id"] == "ghg-gasoline-litre"
    assert response.recommended.rank.temporal == 999


def test_generic_gasoline_does_not_select_jet_gasoline() -> None:
    response = RecommendationEngine().recommend(
        request("gasoline", unit="l"),
        [
            factor(
                "ghg-jet-gasoline-litre",
                name="Jet gasoline stationary combustion",
                source="GHG_PROTOCOL",
                activity_unit="l",
                factor_unit="kgCO2e/l",
                year=None,
            ),
            factor(
                "ghg-motor-gasoline-litre",
                name="Motor gasoline2 stationary combustion",
                source="GHG_PROTOCOL",
                activity_unit="l",
                factor_unit="kgCO2e/l",
                year=None,
            ),
        ],
    )

    assert response.recommended is not None
    assert response.recommended.factor["factor_id"] == "ghg-motor-gasoline-litre"


@pytest.mark.parametrize(
    "name",
    [
        "Aviation gasoline",
        "Jet gasoline stationary combustion",
        "Biogasoline",
        "E85 ethanol/gasoline blend",
        "Bio petrol",
    ],
)
def test_gasoline_projection_excludes_other_fuel_families(name: str) -> None:
    applicability = RecommendationEngine().policy.classify_factor(
        factor("other-gasoline", name=name, source="GHG_PROTOCOL")
    )

    assert applicability is None or applicability["family_code"] != "gasoline"


def test_natural_gas_volume_keeps_energy_factor_and_requests_calorific_value() -> None:
    response = RecommendationEngine().recommend(
        request("natural gas", unit="m3"),
        [factor("ipcc-ng", name="Natural gas", source="IPCC")],
    )

    assert response.status == "conversion_parameter_required"
    assert response.recommended is not None
    assert response.recommended.conversion.required_parameters == ("calorific_value",)
    assert response.calculation is not None
    assert response.calculation.result_value is None


def test_incompatible_unit_never_enters_result_list() -> None:
    response = RecommendationEngine().recommend(
        request("diesel", unit="USD"),
        [factor("ipcc-diesel", name="Diesel stationary combustion", source="IPCC")],
    )

    assert response.status == "no_applicable_factor"
    assert response.recommended is None


def test_electricity_suggest_defaults_to_distribution_and_declares_assumption() -> None:
    distribution = factor(
        "etkb-dist",
        name="Dağıtım Hattından Bağlı Tüketim Noktası — CO2e",
        source="ETKB",
        geography="TR",
        fit="country_specific",
        activity_unit="kWh",
        factor_unit="kgCO2e/kWh",
        scope="Scope 2",
        taxonomy="atlas.energy.electricity.grid_mix",
        activity_type="purchased-electricity",
    )
    transmission = {**distribution, "factor_id": "etkb-trans", "name": "İletim Hattı — CO2e"}

    response = RecommendationEngine().recommend(
        request(
            "electricity",
            unit="kWh",
            profile="corporate_carbon.ghg_protocol.scope2_location",
        ),
        [transmission, distribution],
    )

    assert response.status == "recommended"
    assert response.recommended is not None
    assert response.recommended.factor["factor_id"] == "etkb-dist"
    assert response.assumptions == (
        "Electricity connection level was not supplied; distribution was assumed.",
    )


def test_electricity_suggest_accepts_unqualified_country_factor() -> None:
    country_average = factor(
        "epa-us-average",
        name="US Average / Total Output",
        source="EPA",
        geography="US",
        fit="country_specific",
        activity_unit="kWh",
        factor_unit="kgCO2e/kWh",
        scope="Scope 2",
        taxonomy="atlas.energy.electricity",
        activity_type="electricity",
    )

    response = RecommendationEngine().recommend(
        request(
            "electricity",
            country="US",
            unit="kWh",
            profile="corporate_carbon.ghg_protocol.scope2_location",
        ),
        [country_average],
    )

    assert response.status == "recommended"
    assert response.recommended is not None
    assert response.recommended.factor["factor_id"] == "epa-us-average"
    assert response.recommended.rank.qualifier == 1
    assert "qualifier_unspecified" in response.recommended.reason_codes


def test_explicit_electricity_connection_rejects_unqualified_factor() -> None:
    country_average = factor(
        "epa-us-average",
        name="US Average / Total Output",
        source="EPA",
        geography="US",
        fit="country_specific",
        activity_unit="kWh",
        factor_unit="kgCO2e/kWh",
        scope="Scope 2",
        taxonomy="atlas.energy.electricity",
        activity_type="electricity",
    )

    response = RecommendationEngine().recommend(
        request(
            "electricity",
            country="US",
            unit="kWh",
            profile="corporate_carbon.ghg_protocol.scope2_location",
            qualifiers={"connection_level": "distribution"},
        ),
        [country_average],
    )

    assert response.status == "no_applicable_factor"
    assert response.trace[-1]["details"]["rejected"] == {"qualifier_mismatch": 1}


def test_electricity_strict_requests_connection_level() -> None:
    response = RecommendationEngine().recommend(
        request(
            "electricity",
            unit="kWh",
            profile="corporate_carbon.ghg_protocol.scope2_location",
            mode="strict",
        ),
        [],
    )

    assert response.status == "needs_input"
    assert response.questions[0]["field"] == "facility_context.electricity_connection_level"


def test_electricity_fuel_generation_is_not_purchased_electricity() -> None:
    generation = factor(
        "etkb-gas-generation",
        name="Electricity generation — Natural gas — CO2e",
        source="ETKB",
        geography="TR",
        fit="country_specific",
        activity_unit="kWh",
        factor_unit="kgCO2e/kWh",
        scope="Scope 1",
        taxonomy="atlas.energy.electricity.fuel_generation",
        activity_type="electricity-generation",
    )

    response = RecommendationEngine().recommend(
        request(
            "electricity",
            unit="kWh",
            profile="corporate_carbon.ghg_protocol.scope2_location",
        ),
        [generation],
    )

    assert response.status == "no_applicable_factor"


def test_jurisdiction_authority_is_country_specific() -> None:
    epa = factor(
        "epa-diesel",
        name="Diesel stationary combustion",
        source="EPA",
        geography="US",
        fit="country_specific",
    )
    ipcc = factor("ipcc-diesel", name="Diesel stationary combustion", source="IPCC")

    response = RecommendationEngine().recommend(
        request("diesel", country="US"), [ipcc, epa]
    )

    assert response.recommended is not None
    assert response.recommended.factor["factor_id"] == "epa-diesel"
    assert response.recommended.rank.tier == "country_official"


def test_foreign_proxy_requires_explicit_acceptance() -> None:
    defra = factor(
        "defra-flight",
        name="Business travel / Flights / Domestic / Average passenger",
        source="DEFRA",
        geography="GB",
        fit="country_specific",
        activity_unit="passenger.km",
        factor_unit="kgCO2e/passenger.km",
        scope="Scope 3",
        taxonomy="atlas.transport.air.domestic.passenger",
        activity_type="passenger-distance",
    )
    base = request(
        "domestic flight",
        country="TR",
        unit="passenger",
        profile="corporate_carbon.ghg_protocol.scope3",
    )

    denied = RecommendationEngine().recommend(base, [defra])
    accepted = RecommendationEngine().recommend(
        base.model_copy(update={"accept_proxy": True}), [defra]
    )

    assert denied.status == "no_applicable_factor"
    assert accepted.status == "conversion_parameter_required"
    assert accepted.recommended is not None
    assert accepted.recommended.rank.tier == "foreign_proxy"
    assert accepted.recommended.conversion.required_parameters == ("distance",)


def test_education_service_uses_spend_classification_and_currency_contract() -> None:
    education = factor(
        "ceda-education",
        name="Colleges, universities, and professional schools — Turkey",
        source="OPEN_CEDA",
        geography="TR",
        fit="country_modelled",
        activity_unit="USD_2022_producer_price",
        factor_unit="kgCO2e/USD_2022_producer_price",
        scope="Scope 3",
        taxonomy="atlas.spend.economic_sector.611310",
        activity_type="spend",
    )

    response = RecommendationEngine().recommend(
        request(
            "education service",
            country="TR",
            unit="TRY",
            profile="corporate_carbon.ghg_protocol.scope3",
        ),
        [education],
    )

    assert response.status == "conversion_parameter_required"
    assert response.intent.family_code == "purchased_services"
    assert response.recommended is not None
    assert response.recommended.conversion.required_parameters == ("exchange_rate",)


def test_scope3_strict_requires_explicit_category() -> None:
    response = RecommendationEngine().recommend(
        request(
            "domestic flight",
            country="GB",
            unit="passenger.km",
            profile="corporate_carbon.ghg_protocol.scope3",
            mode="strict",
        ),
        [],
    )

    assert response.status == "needs_input"
    assert response.questions[0]["field"] == "activity.scope3_category"
    assert [item["code"] for item in response.questions[0]["options"]] == [6]


def test_scope3_category_is_rejected_outside_scope3_profile() -> None:
    with pytest.raises(ValueError, match="requires a Scope 3 calculation profile"):
        request("natural gas", scope3_category=3)


def test_scope3_suggest_infers_unambiguous_business_travel_category() -> None:
    flight = factor(
        "defra-flight",
        name="Business travel / Flights / Domestic / Average passenger",
        source="DEFRA",
        geography="GB",
        fit="country_specific",
        activity_unit="passenger.km",
        factor_unit="kgCO2e/passenger.km",
        scope="Scope 3",
        taxonomy="atlas.transport.air.domestic.passenger",
        activity_type="passenger-distance",
    )

    response = RecommendationEngine().recommend(
        request(
            "domestic flight",
            country="GB",
            unit="passenger.km",
            profile="corporate_carbon.ghg_protocol.scope3",
        ),
        [flight],
    )

    assert response.status == "recommended"
    assert response.intent.scope3_category == 6
    assert "Scope 3 category 6 (Business travel)" in response.assumptions[0]
    assert response.recommended is not None
    assert response.recommended.applicability["scope3_categories"] == (6,)
    assert "scope3_category_exact" in response.recommended.reason_codes


def test_scope3_ambiguous_freight_direction_requires_category() -> None:
    response = RecommendationEngine().recommend(
        request(
            "road freight",
            country="US",
            unit="tonne.km",
            profile="corporate_carbon.ghg_protocol.scope3",
        ),
        [],
    )

    assert response.status == "needs_input"
    assert [item["code"] for item in response.questions[0]["options"]] == [4, 9]


def test_scope3_explicit_category_rejects_incompatible_family() -> None:
    response = RecommendationEngine().recommend(
        request(
            "road freight",
            country="US",
            unit="tonne.km",
            profile="corporate_carbon.ghg_protocol.scope3",
            scope3_category=6,
        ),
        [],
    )

    assert response.status == "no_applicable_factor"
    assert response.trace[-1]["stage"] == "scope3_category"
    assert response.trace[-1]["details"]["reason"] == "family_category_mismatch"


def test_scope3_waste_requires_material_and_treatment_before_selection() -> None:
    missing = RecommendationEngine().recommend(
        request(
            "waste",
            country="US",
            unit="kg",
            profile="corporate_carbon.ghg_protocol.scope3",
            scope3_category=5,
        ),
        [],
    )

    assert missing.status == "needs_input"
    assert [item["field"] for item in missing.questions] == [
        "activity.qualifiers.material",
        "activity.qualifiers.treatment",
    ]

    aluminum = factor(
        "epa-aluminum-landfill",
        name="Aluminum Cans / Landfilled",
        source="EPA",
        geography="US",
        fit="country_specific",
        activity_unit="kg",
        factor_unit="kgCO2e/kg",
        scope="Scope 3",
        taxonomy="atlas.waste",
        activity_type="waste",
    )
    aluminum["methodology"]["details"] = {"material": "Aluminum Cans"}
    plastic = {
        **aluminum,
        "factor_id": "epa-plastic-landfill",
        "name": "Mixed Plastics / Landfilled",
        "methodology": {
            **aluminum["methodology"],
            "details": {"material": "Mixed Plastics"},
        },
    }
    selected = RecommendationEngine().recommend(
        request(
            "waste landfill",
            country="US",
            unit="kg",
            profile="corporate_carbon.ghg_protocol.scope3",
            scope3_category=5,
            qualifiers={"material": "Mixed Plastics"},
        ),
        [aluminum, plastic],
    )

    assert selected.status == "recommended"
    assert selected.recommended is not None
    assert selected.recommended.factor["factor_id"] == "epa-plastic-landfill"


@pytest.mark.parametrize("query", ["Natural gas", "Doğal gaz", "Erdgas", "Gaz naturel"])
def test_multilingual_natural_gas_resolves_same_family(query: str) -> None:
    response = RecommendationEngine().recommend(
        request(query), [factor("ipcc-ng", name="Natural gas", source="IPCC")]
    )

    assert response.intent.family_code == "natural_gas"
    assert response.recommended is not None
