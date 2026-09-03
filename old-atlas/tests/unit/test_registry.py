from pathlib import Path

import pytest

from atlas.domain.enums import EnvironmentalEntityType, SourceHistoryStrategy
from atlas.domain.models import SourceDefinition
from atlas.ingestion.registry import SourceNotFoundError, SourceRegistry


def test_discovers_first_phase_source_manifests() -> None:
    registry = SourceRegistry.discover(Path("sources"))

    assert [source.code for source in registry.list()] == [
        "ADEME",
        "AGRIBALYSE",
        "AIB",
        "CANADA",
        "CBAM",
        "CONCITO",
        "DEFRA",
        "EEA",
        "EMBER",
        "EPA",
        "ETKB",
        "GHG_PROTOCOL",
        "GLEC",
        "IPCC",
        "OEKOBAUDAT",
        "OPEN_CEDA",
        "PLASTICS_EUROPE",
        "PLASTICS_RECYCLERS_EUROPE",
        "UNFCCC_TUIK",
        "WRAP",
    ]
    assert registry.get("defra").adapter.parser_version == "0.2.0"
    assert [item.code for item in registry.get("DEFRA").coverage] == ["GB"]
    assert [item.code for item in registry.get("EPA").coverage] == ["US", "GLOBAL"]
    assert registry.get("DEFRA").history.reference_years == tuple(range(2020, 2027))
    assert registry.get("DEFRA").history.schema_for(2021).name == "legacy_flat_file"
    assert registry.get("DEFRA").history.schema_for(2026).name == "identified_flat_file"
    assert registry.get("EPA").history.reference_years == tuple(range(2020, 2026))
    assert registry.get("ETKB").history.reference_years == tuple(range(2020, 2024))
    assert registry.get("ETKB").data_types == (EnvironmentalEntityType.EMISSION_FACTOR,)
    assert registry.get("AIB").history.publication_lag_years == 1
    assert registry.get("AIB").history.schema_for(2021).implemented is False
    assert registry.get("IPCC").history.strategy == SourceHistoryStrategy.VERSIONED_DATABASE
    assert registry.get("GLEC").history.strategy == SourceHistoryStrategy.VERSIONED_DATABASE
    assert registry.get("GHG_PROTOCOL").history.strategy == SourceHistoryStrategy.VERSIONED_DATABASE
    assert registry.get("CBAM").history.strategy == SourceHistoryStrategy.VERSIONED_DATABASE
    assert registry.get("CANADA").history.strategy == SourceHistoryStrategy.VERSIONED_DATABASE
    assert registry.get("CANADA").data_types == (
        EnvironmentalEntityType.EMISSION_FACTOR,
        EnvironmentalEntityType.CALCULATION_PARAMETER,
        EnvironmentalEntityType.REFERENCE_VALUE,
    )
    assert registry.get("CBAM").data_types == (
        EnvironmentalEntityType.EMBODIED_EMISSION_FACTOR,
        EnvironmentalEntityType.CALCULATION_PARAMETER,
    )
    assert registry.get("GHG_PROTOCOL").data_types == (
        EnvironmentalEntityType.EMISSION_FACTOR,
        EnvironmentalEntityType.CONVERSION_FACTOR,
        EnvironmentalEntityType.TECHNICAL_PROPERTY,
    )
    assert registry.get("GLEC").data_types == (
        EnvironmentalEntityType.EMISSION_FACTOR,
        EnvironmentalEntityType.CHARACTERIZATION_RESULT,
        EnvironmentalEntityType.CALCULATION_PARAMETER,
    )
    assert registry.get("IPCC").history.reference_years == ()
    assert registry.get("ADEME").history.strategy == SourceHistoryStrategy.VERSIONED_DATABASE
    assert registry.get("AGRIBALYSE").history.strategy == SourceHistoryStrategy.VERSIONED_DATABASE
    assert registry.get("AGRIBALYSE").data_types == (
        EnvironmentalEntityType.LCA_RESULT,
        EnvironmentalEntityType.CHARACTERIZATION_RESULT,
    )
    assert registry.get("OEKOBAUDAT").history.strategy == (SourceHistoryStrategy.VERSIONED_DATABASE)
    assert registry.get("OEKOBAUDAT").data_types == (EnvironmentalEntityType.LCA_RESULT,)
    assert registry.get("WRAP").history.strategy == SourceHistoryStrategy.VERSIONED_DATABASE
    assert registry.get("WRAP").data_types == (EnvironmentalEntityType.LCA_RESULT,)
    assert registry.get("CONCITO").history.strategy == (SourceHistoryStrategy.VERSIONED_DATABASE)
    assert registry.get("CONCITO").data_types == (EnvironmentalEntityType.LCA_RESULT,)
    assert registry.get("PLASTICS_EUROPE").data_types == (EnvironmentalEntityType.LCA_RESULT,)
    assert registry.get("PLASTICS_RECYCLERS_EUROPE").data_types == (
        EnvironmentalEntityType.LCA_RESULT,
        EnvironmentalEntityType.CALCULATION_PARAMETER,
    )
    assert registry.get("EMBER").history.strategy == SourceHistoryStrategy.API_TIME_SERIES
    assert registry.get("EEA").history.strategy == SourceHistoryStrategy.VERSIONED_DATABASE
    assert registry.get("EEA").data_types == (
        EnvironmentalEntityType.EMISSION_FACTOR,
        EnvironmentalEntityType.CALCULATION_PARAMETER,
    )
    assert registry.get("EMBER").history.supports_targeted_backfill is False
    assert registry.get("UNFCCC_TUIK").history.strategy == SourceHistoryStrategy.YEARLY_SUBMISSION
    assert registry.get("UNFCCC_TUIK").history.reference_years == tuple(range(2020, 2027))
    assert registry.get("UNFCCC_TUIK").history.schema_for(2020).name == "crf_legacy"
    assert registry.get("UNFCCC_TUIK").history.schema_for(2024).name == "crt_etf"
    assert registry.get("OPEN_CEDA").history.reference_years == (2024, 2025)
    assert registry.get("OPEN_CEDA").history.schema_for(2024).parser_version == "0.1.0"
    assert registry.get("OPEN_CEDA").history.schema_for(2025).parser_version == "0.2.0"
    assert registry.get("OPEN_CEDA").data_types == (
        EnvironmentalEntityType.EMISSION_FACTOR,
        EnvironmentalEntityType.CALCULATION_PARAMETER,
    )


def test_unknown_source_is_explicit() -> None:
    registry = SourceRegistry.discover(Path("sources"))

    with pytest.raises(SourceNotFoundError):
        registry.get("UNKNOWN")


def test_api_time_series_is_a_snapshot_not_synthetic_annual_releases() -> None:
    manifest = SourceRegistry.load_manifest(Path("sources/ipcc/manifest.yaml")).model_dump(
        mode="json"
    )
    manifest["code"] = "EMBER"
    manifest["name"] = "Ember"
    manifest["history"]["strategy"] = "api_time_series"
    manifest["history"]["snapshot_endpoints"] = {
        "yearly_carbon_intensity": "https://api.ember-energy.org/v1/carbon-intensity/yearly"
    }
    manifest["data_types"] = ["emission_factor", "activity_data"]

    source = SourceDefinition.model_validate(manifest)

    assert source.history.reference_years == ()
    assert source.history.supports_targeted_backfill is False
    assert source.data_types == (
        EnvironmentalEntityType.EMISSION_FACTOR,
        EnvironmentalEntityType.ACTIVITY_DATA,
    )
