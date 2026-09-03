from __future__ import annotations

import os
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from atlas.domain.enums import (
    EnvironmentalEntityType,
    FactorValueKind,
    GeographicFitType,
)
from atlas.domain.models import RawAssetReference
from atlas.geography import GeographicCoverageEngine
from atlas.ingestion.errors import PermanentIngestionError
from atlas.validation import QualityEngine
from sources.canada.normalizer import CanadaNormalizer
from sources.canada.parser import (
    CanadaFactorRow,
    CanadaObservationRow,
    CanadaParser,
)


def _raw() -> RawAssetReference:
    return RawAssetReference(
        bucket="atlas-raw",
        object_key="sources/canada/v3.0/test.html",
        sha256="d" * 64,
        filename="canada-emission-factors-reference-values-v3.html",
        source_url="https://example.test/canada-v3.html",
        size_bytes=123,
        downloaded_at=datetime.now(UTC),
    )


def test_canada_normalizer_preserves_gas_and_observation_semantics() -> None:
    factors = (
        CanadaFactorRow(
            table_number="5.3",
            table_title="Electricity consumption intensity for 2026",
            source_row=1,
            source_column=2,
            name="Alberta",
            category="Electricity",
            variant="Consumption intensity",
            gas="CO2e",
            value=Decimal("438"),
            original_unit="gCO2e/kWh",
            reference_year=2026,
            valid_from_year=2026,
            valid_to_year=2026,
            geography_name="Alberta",
        ),
        CanadaFactorRow(
            table_number="6.2",
            table_title="Biogas combustion factor for 2025",
            source_row=1,
            source_column=2,
            name="Continuous flare",
            category="Biogas combustion",
            variant="Continuous flare",
            gas="N2O",
            value=Decimal("0.11"),
            original_unit="kgN2O/tCH4",
            reference_year=2025,
            valid_from_year=2025,
            valid_to_year=2025,
        ),
    )
    observations = (
        CanadaObservationRow(
            table_number="11",
            table_title="Manure parameters",
            source_row=1,
            source_column=2,
            name="Pasture — MCF",
            parameter_code="MCF",
            value=Decimal("0.01"),
            unit="dimensionless",
            entity_type=EnvironmentalEntityType.CALCULATION_PARAMETER,
            protocol="Reducing Enteric Methane Emissions from Beef Cattle",
            valid_from_year=2025,
            original_column_name="MCF",
        ),
    )

    normalized, source_observations, metrics = CanadaNormalizer(
        Path("sources/canada/mappings.yaml")
    ).normalize(
        factors,
        observations,
        raw=_raw(),
        version="3.0",
        parser_version="0.1.0",
    )

    electricity, biogas = normalized
    assert electricity.factor_value == Decimal("0.438")
    assert electricity.factor_unit == "kgCO2e/kWh"
    assert electricity.factor_value_kind == FactorValueKind.CO2E_TOTAL
    assert electricity.default_match_eligible is True
    assert electricity.origin_geography is not None
    assert electricity.origin_geography.code == "CA-AB"
    assert electricity.geographic_fit_type == GeographicFitType.COUNTRY_SPECIFIC
    assert biogas.factor_value == Decimal("0.00011")
    assert biogas.factor_unit == "kgN2O/kgCH4"
    assert biogas.factor_value_kind == FactorValueKind.GAS_EMISSION_FACTOR
    assert biogas.default_match_eligible is False
    assert source_observations[0].entity_type == EnvironmentalEntityType.CALCULATION_PARAMETER
    assert metrics["normalized_factors"] == 2
    assert metrics["source_observations"] == 1


def test_canada_parser_rejects_an_unrelated_html_document(tmp_path: Path) -> None:
    path = tmp_path / "invalid.html"
    path.write_text("<html><h1>Unrelated</h1></html>", encoding="utf-8")

    with pytest.raises(PermanentIngestionError, match="title changed"):
        CanadaParser().parse(path)


def test_canada_provinces_are_exact_geographies() -> None:
    engine = GeographicCoverageEngine()

    assert engine.ancestors("CA-AB") == ("CA", "NORTH_AMERICA", "GLOBAL")
    evaluation = engine.evaluate(
        "CA-AB",
        {
            "geographic_fit_type": "country_specific",
            "geography_level": "province",
            "applicable_geographies": [
                {"level": "province", "code": "CA-AB", "name": "Alberta"},
                {"level": "country", "code": "CA", "name": "Canada"},
            ],
        },
    )
    assert evaluation.exact_geography is True
    assert evaluation.fallback_used is False


@pytest.mark.skipif(
    not os.getenv("ATLAS_CANADA_EFRV_HTML"),
    reason="set ATLAS_CANADA_EFRV_HTML to run the official Version 3.0 snapshot",
)
def test_official_canada_version_3_snapshot() -> None:
    path = Path(os.environ["ATLAS_CANADA_EFRV_HTML"])
    parser = CanadaParser()
    document = parser.parse(path)
    factors, observations, metrics = CanadaNormalizer(
        Path("sources/canada/mappings.yaml")
    ).normalize(
        document.factors,
        document.observations,
        raw=_raw(),
        version=document.version,
        parser_version="0.1.0",
    )

    assert parser.metrics == {
        "parsed_rows": 444,
        "parsed_factor_rows": 399,
        "parsed_observations": 45,
        "source_tables": 24,
        "table_1_factors": 69,
        "table_2_factors": 60,
        "table_3_factors": 36,
        "table_4_factors": 189,
        "table_5_factors": 39,
        "table_6_factors": 6,
        "table_10_observations": 6,
        "table_11_observations": 12,
        "table_12_observations": 8,
        "table_7_observations": 6,
        "table_8_observations": 8,
        "table_9_observations": 5,
    }
    assert len(factors) == 399
    assert len({factor.factor_id for factor in factors}) == 399
    assert len(observations) == 45
    assert len({item.observation_id for item in observations}) == 45
    assert metrics["co2_only_factors"] == 144
    assert metrics["gas_emission_factors"] == 216
    assert metrics["co2e_total_factors"] == 39
    assert metrics["default_match_eligible"] == 39
    assert metrics["country_specific_factors"] == 395
    assert metrics["proxy_factors"] == 4
    assert QualityEngine().validate(factors).findings == ()
    assert Counter(item.entity_type for item in observations) == {
        EnvironmentalEntityType.CALCULATION_PARAMETER: 31,
        EnvironmentalEntityType.REFERENCE_VALUE: 14,
    }
    explicit_volume = next(
        factor
        for factor in factors
        if factor.name == "Still Gas - Refineries and Others — CO2"
        and factor.reference_year == 2023
    )
    assert explicit_volume.factor_unit == "kgCO2/m3"
