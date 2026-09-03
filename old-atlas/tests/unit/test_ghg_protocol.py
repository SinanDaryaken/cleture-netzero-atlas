from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from atlas.domain.enums import (
    EnvironmentalEntityType,
    FactorIntendedUse,
    FactorValueKind,
    GeographicFitType,
    GeographyLevel,
)
from atlas.domain.models import RawAssetReference
from atlas.ingestion.errors import PermanentIngestionError
from sources.ghg_protocol.normalizer import GhgProtocolNormalizer
from sources.ghg_protocol.parser import (
    GhgProtocolFactorRow,
    GhgProtocolObservationRow,
    GhgProtocolParser,
)


def _raw() -> RawAssetReference:
    return RawAssetReference(
        bucket="atlas-raw",
        object_key="sources/ghg_protocol/v2.0/test.xlsx",
        sha256="d" * 64,
        filename="cross-sector-v2.0.xlsx",
        source_url="https://example.test/cross-sector-v2.0.xlsx",
        size_bytes=123,
        downloaded_at=datetime.now(UTC),
    )


def test_normalizer_preserves_total_partial_and_observation_semantics() -> None:
    rows = (
        GhgProtocolFactorRow(
            source_sheet="Electricity US",
            source_table="Table 1",
            source_row=6,
            source_key="electricity-us-2022-ascc-alaska-grid",
            name="ASCC Alaska Grid electricity",
            category="Purchased electricity",
            activity_type="purchased-electricity",
            geography_code="ASCC Alaska Grid",
            geography_name="ASCC Alaska Grid",
            denominator_unit="MWh",
            co2=Decimal("1000"),
            co2_unit="lb/MWh",
            ch4=Decimal("100"),
            ch4_unit="lb/GWh",
            n2o=Decimal("10"),
            n2o_unit="lb/GWh",
            factor_value_kind=FactorValueKind.CO2E_TOTAL,
            reference_year=2022,
            scope="scope 2",
            lifecycle_stage="generation",
            system_boundary="grid generation",
            original_source="US EPA eGRID",
        ),
        GhgProtocolFactorRow(
            source_sheet="Mobile Combustion - Fuel Use",
            source_table="Table 1",
            source_row=30,
            source_key="biogenic-ethanol",
            name="Ethanol biogenic CO2",
            category="Mobile combustion - fuel use",
            activity_type="mobile-combustion-fuel",
            geography_code="US",
            geography_name="United States",
            denominator_unit="US Gallon",
            co2=Decimal("5.75"),
            co2_unit="kg/US Gallon",
            factor_value_kind=FactorValueKind.CO2_ONLY,
            intended_use=FactorIntendedUse.CALCULATION_INPUT,
            scope="outside scopes",
            lifecycle_stage="tank-to-wheel",
            system_boundary="direct combustion",
            original_source="US EPA",
        ),
    )
    observations = (
        GhgProtocolObservationRow(
            observation_kind="conversion_factor",
            source_sheet="Abbreviations and Conversions",
            source_table="Energy conversions",
            source_row=6,
            source_column=4,
            name="GJ to kWh",
            value=Decimal("277.777777778"),
            unit="kWh/GJ",
            category="Energy conversions",
        ),
    )
    factors, normalized_observations, metrics = GhgProtocolNormalizer(
        Path("sources/ghg_protocol/mappings.yaml")
    ).normalize(rows, observations, raw=_raw(), version="2.0", parser_version="0.1.0")

    assert len(factors) == 2
    electricity = factors[0]
    assert electricity.factor_value == Decimal("0.4560644484165")
    assert electricity.factor_unit == "kgCO2e/kWh"
    assert electricity.factor_value_kind == FactorValueKind.CO2E_TOTAL
    assert electricity.default_match_eligible is True
    assert electricity.geography_level == GeographyLevel.GRID
    assert electricity.geographic_fit_type == GeographicFitType.REGIONAL
    assert electricity.origin_geography is not None
    assert electricity.origin_geography.code == "AKGD"
    assert len(electricity.component_provenance) == 3

    biogenic = factors[1]
    assert biogenic.factor_value == Decimal("5.75") / Decimal("3.785411784")
    assert biogenic.factor_unit == "kgCO2/l"
    assert biogenic.intended_use == FactorIntendedUse.CALCULATION_INPUT
    assert biogenic.default_match_eligible is False

    assert normalized_observations[0].entity_type == EnvironmentalEntityType.CONVERSION_FACTOR
    assert metrics["default_match_eligible"] == 1


def test_normalizer_excludes_range_values_without_inventing_a_midpoint() -> None:
    row = GhgProtocolFactorRow(
        source_sheet="Mobile Combustion - Distance",
        source_table="Table 1",
        source_row=22,
        source_key="range",
        name="Range-valued vehicle factor",
        category="Mobile combustion - vehicle distance",
        activity_type="vehicle-distance",
        geography_code="GLOBAL",
        geography_name="Global",
        denominator_unit="km",
        ch4="0.215 - 0.725",
        ch4_unit="g/km",
        n2o="0.027 - 0.07",
        n2o_unit="g/km",
        factor_value_kind=FactorValueKind.NON_CO2_CO2E,
        scope="scope 1",
        lifecycle_stage="tank-to-wheel",
        system_boundary="direct vehicle operation",
        original_source="IPCC",
    )

    factors, _, metrics = GhgProtocolNormalizer(
        Path("sources/ghg_protocol/mappings.yaml")
    ).normalize((row,), (), raw=_raw(), version="2.0", parser_version="0.1.0")

    assert factors == ()
    assert metrics["excluded_range_values"] == 1


def test_parser_rejects_an_unreadable_workbook(tmp_path: Path) -> None:
    path = tmp_path / "invalid.xlsx"
    path.write_bytes(b"not an XLSX")

    with pytest.raises(PermanentIngestionError, match=r"not a readable Cross-sector v2\.0"):
        GhgProtocolParser().parse(path)


@pytest.mark.skipif(
    not os.getenv("ATLAS_GHG_PROTOCOL_XLSX"),
    reason="set ATLAS_GHG_PROTOCOL_XLSX to run the official Cross-sector v2.0 snapshot",
)
def test_official_cross_sector_v2_snapshot() -> None:
    path = Path(os.environ["ATLAS_GHG_PROTOCOL_XLSX"])
    parser = GhgProtocolParser()
    parsed = parser.parse(path)
    factors, observations, metrics = GhgProtocolNormalizer(
        Path("sources/ghg_protocol/mappings.yaml")
    ).normalize(
        parsed.factors,
        parsed.observations,
        raw=_raw(),
        version=parsed.version,
        parser_version="0.1.0",
    )

    assert parser.metrics == {
        "parsed_rows": 1036,
        "parsed_factor_rows": 878,
        "parsed_observations": 158,
        "range_valued_factor_rows": 3,
    }
    assert len(factors) == 875
    assert len({factor.factor_id for factor in factors}) == 875
    assert len(observations) == 158
    assert len({observation.observation_id for observation in observations}) == 158
    assert metrics["co2e_total_factors"] == 606
    assert metrics["co2_only_factors"] == 58
    assert metrics["non_co2_factors"] == 211
    assert metrics["excluded_range_values"] == 3
