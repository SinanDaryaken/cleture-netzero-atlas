from typing import Any

from atlas.recommendation import RecommendationPolicy
from atlas.semantics import (
    DraftTranslator,
    MultilingualConceptResolver,
    OpenAITranslationProvider,
    ResolvableTerm,
    SemanticRegistry,
    TranslationInput,
)


def _factor(*, entity_type: str, factor_kind: str, intended_use: str) -> dict[str, Any]:
    return {
        "entity_type": entity_type,
        "factor_value_kind": factor_kind,
        "intended_use": intended_use,
    }


def test_turkish_synonym_resolves_to_one_canonical_concept() -> None:
    registry = SemanticRegistry()

    assert registry.match_concepts("doğalgaz", language="tr") == ("energy.natural_gas",)
    assert registry.match_concepts("doğal gaz tüketimi", language="tr") == ("energy.natural_gas",)


def test_wheat_translations_resolve_to_one_canonical_concept() -> None:
    registry = SemanticRegistry()

    resolutions = [
        registry.resolve_concept(query).concept_code
        for query in ("Wheat", "Buğday", "Blé", "Weizen")
    ]

    assert resolutions == ["agriculture.wheat"] * 4


def test_diesel_translations_resolve_to_one_canonical_concept() -> None:
    registry = SemanticRegistry()

    resolutions = [
        registry.resolve_concept(query).concept_code
        for query in ("Diesel", "Diesel oil", "Motorin", "Mazot", "Gazole")
    ]

    assert resolutions == ["energy.diesel"] * 5


def test_vehicle_aliases_resolve_across_catalog_languages() -> None:
    registry = SemanticRegistry()

    expected = {
        "T\u0131r": "transport.freight.road",
        "Lkw": "transport.freight.road",
        "camión": "transport.freight.road",
        "грузовик": "transport.freight.road",
        "شاحنة": "transport.freight.road",
        "Araba": "transport.road.passenger",
        "voiture": "transport.road.passenger",
        "Panelvan": "transport.road.delivery",
        "van": "transport.road.delivery",
        "Lieferwagen": "transport.road.delivery",
        "furgoneta": "transport.road.delivery",
    }

    assert {query: registry.resolve_concept(query).concept_code for query in expected} == expected


def test_gasoline_translations_resolve_to_one_canonical_concept() -> None:
    registry = SemanticRegistry()

    resolutions = [
        registry.resolve_concept(query).concept_code
        for query in (
            "Gasoline",
            "Motor gasoline",
            "Petrol",
            "Benzin",
            "Ottokraftstoff",
            "Essence",
            "Gasolina",
            "Бензин",
            "بنزين",
        )
    ]

    assert resolutions == ["energy.gasoline"] * 9


def test_corporate_profile_denies_lca_result_even_when_text_matches() -> None:
    decision = SemanticRegistry().evaluate(
        "corporate_carbon.ghg_protocol.scope3",
        _factor(
            entity_type="lca_result",
            factor_kind="co2e_total",
            intended_use="characterization",
        ),
    )

    assert decision.search_eligible is True
    assert decision.calculation_eligible is False
    assert set(decision.reason_codes) == {
        "entity_type_denied",
        "intended_use_denied",
        "scope_unknown",
    }


def test_lca_profile_accepts_lca_characterization_result() -> None:
    decision = SemanticRegistry().evaluate(
        "lca.iso14040",
        _factor(
            entity_type="lca_result",
            factor_kind="co2e_total",
            intended_use="characterization",
        ),
    )

    assert decision.calculation_eligible is True
    assert decision.reason_codes == ()


def test_scope1_profile_denies_scope3_factor() -> None:
    factor = _factor(
        entity_type="emission_factor",
        factor_kind="co2e_total",
        intended_use="inventory",
    )
    factor["methodology"] = {"scope": "Scope 3"}

    decision = SemanticRegistry().evaluate("corporate_carbon.ghg_protocol.scope1", factor)

    assert decision.calculation_eligible is False
    assert decision.reason_codes == ("scope_denied",)


def test_scope1_profile_infers_national_inventory_energy_scope() -> None:
    factor = _factor(
        entity_type="emission_factor",
        factor_kind="co2e_total",
        intended_use="inventory",
    )
    factor.update(
        {
            "concept_code": "energy.diesel",
            "activity_type": "energy",
            "methodology": {
                "scope": None,
                "system_boundary": "national_inventory_implied_factor",
            },
        }
    )

    decision = SemanticRegistry().evaluate("corporate_carbon.ghg_protocol.scope1", factor)

    assert decision.calculation_eligible is True
    assert decision.reason_codes == ()


def test_published_catalog_search_does_not_apply_runtime_license_denial() -> None:
    factor = _factor(
        entity_type="emission_factor",
        factor_kind="co2e_total",
        intended_use="inventory",
    )
    factor.update({"methodology": {"scope": "scope_1"}, "license_eligible": False})

    decision = SemanticRegistry().evaluate("corporate_carbon.ghg_protocol.scope1", factor)

    assert decision.calculation_eligible is True
    assert "license_denied" not in decision.reason_codes


def test_cbam_profile_only_accepts_embodied_calculation_input() -> None:
    registry = SemanticRegistry()
    accepted = registry.evaluate(
        "cbam.eu_definitive",
        _factor(
            entity_type="embodied_emission_factor",
            factor_kind="co2e_total",
            intended_use="calculation_input",
        ),
    )
    denied = registry.evaluate(
        "cbam.eu_definitive",
        _factor(
            entity_type="emission_factor",
            factor_kind="co2e_total",
            intended_use="inventory",
        ),
    )

    assert accepted.calculation_eligible is True
    assert denied.calculation_eligible is False


def test_machine_translation_is_always_a_review_required_draft() -> None:
    translator = DraftTranslator(
        lambda text, source, target: f"{text}:{source}->{target}",
        model="argos-test",
    )

    label = translator.draft("Natural gas", "en", "tr")

    assert label.method == "argos"
    assert label.review_status == "draft"
    assert label.model == "argos-test"


def test_registry_declares_every_supported_search_language() -> None:
    assert SemanticRegistry().target_languages() == ("en", "tr", "de", "fr", "es", "ru", "ar")


def test_multilingual_resolver_preserves_non_latin_queries() -> None:
    resolver = MultilingualConceptResolver()
    terms = [
        ResolvableTerm(
            concept_code="energy.electricity",
            family="energy",
            language="ru",
            term="Электричество",
            kind="translation",
            is_preferred=True,
        ),
        ResolvableTerm(
            concept_code="energy.electricity",
            family="energy",
            language="ar",
            term="الكهرباء",
            kind="translation",
            is_preferred=True,
        ),
    ]

    russian = resolver.resolve("Электричество", terms)
    arabic = resolver.resolve("الكهرباء", terms)

    assert russian.normalized_query == "электричество"
    assert russian.candidates[0].concept_code == "energy.electricity"
    assert arabic.normalized_query == "الكهرباء"
    assert arabic.candidates[0].concept_code == "energy.electricity"


def test_multilingual_resolver_does_not_match_one_generic_overlapping_token() -> None:
    resolution = MultilingualConceptResolver().resolve(
        "energy service",
        [
            ResolvableTerm(
                concept_code="energy.electricity",
                family="energy",
                language="en",
                term="electrical energy",
                kind="translation",
                is_preferred=True,
            )
        ],
    )

    assert resolution.status == "unresolved"
    assert resolution.candidates == ()


def test_non_latin_unknown_query_never_defaults_to_first_recommendation_family() -> None:
    family, definition = RecommendationPolicy().resolve_family("электричество")

    assert family == "unknown"
    assert definition["concept_code"] is None


def test_openai_translation_prompt_uses_context_and_protected_glossary() -> None:
    item = TranslationInput(
        concept_code="energy.natural_gas",
        family="energy",
        canonical_name_en="Natural gas combustion",
        definition_en="Stationary combustion of natural gas.",
        taxonomy_path="atlas.energy.natural_gas",
        sample_factor_names=("Natural gas — stationary combustion",),
        activity_types=("fuel",),
    )

    instructions = OpenAITranslationProvider._instructions("tr", ("CO2e", "Scope 1"))
    input_text = OpenAITranslationProvider._input_text(item, "tr")

    assert "not as a word-for-word template" in instructions
    assert "CO2e, Scope 1" in instructions
    assert '"concept_code": "energy.natural_gas"' in input_text
    assert '"sample_factor_names": ["Natural gas — stationary combustion"]' in input_text


def test_openai_batch_response_extracts_structured_output_text() -> None:
    body = {
        "output": [
            {
                "content": [
                    {
                        "type": "output_text",
                        "text": '{"preferred_term":"Doğal gaz","definition":"Gaz.",'
                        '"synonyms":[],"abbreviations":[],"protected_terms":[],'
                        '"warnings":[]}',
                    }
                ]
            }
        ]
    }

    output = OpenAITranslationProvider._response_output_text(body)

    assert '"preferred_term":"Doğal gaz"' in output
