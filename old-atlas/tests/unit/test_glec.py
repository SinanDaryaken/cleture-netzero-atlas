from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from atlas.domain.enums import (
    EnvironmentalEntityType,
    FactorIntendedUse,
    GeographicFitType,
)
from atlas.domain.models import RawAssetReference
from atlas.ingestion.errors import PermanentIngestionError
from sources.glec.normalizer import GlecNormalizer
from sources.glec.parser import (
    GlecFuelRow,
    GlecIntensityRow,
    GlecParameterRow,
    GlecParser,
    GlecRefrigerantRow,
)


def _raw() -> RawAssetReference:
    return RawAssetReference(
        bucket="atlas-raw",
        object_key="sources/glec/v3.2/test.pdf",
        sha256="c" * 64,
        filename="glec-framework-v3.2.pdf",
        source_url="https://example.test/glec-framework-v3.2.pdf",
        size_bytes=123,
        downloaded_at=datetime.now(UTC),
    )


def test_glec_normalizer_keeps_factor_and_parameter_semantics_separate() -> None:
    fuel = GlecFuelRow(
        geography_code="EU",
        geography_name="Europe",
        energy_carrier="Diesel",
        application=None,
        ttw_g_co2e_per_mj=Decimal("75.3"),
        wtw_g_co2e_per_mj=Decimal("97.8"),
        source_page=77,
        source_table="Module 1 Table 1",
    )
    intensity = GlecIntensityRow(
        mode="road",
        geography_code="CN",
        geography_name="China",
        category="Rigid truck",
        detail="Average",
        fuel="Diesel",
        activity_unit="tkm",
        wtw_value=Decimal("120"),
        wtt_value=Decimal("20"),
        ttw_value=Decimal("100"),
        source_unit="gCO2e/tkm",
        source_page=103,
        source_table="Module 2 Table 12",
    )
    refrigerants = (
        GlecRefrigerantRow(refrigerant="R-134a", gwp100_ar6=Decimal("1530")),
        GlecRefrigerantRow(refrigerant="R-717", gwp100_ar6=None),
    )
    parameter = GlecParameterRow(
        name="Annual leakage rate",
        equipment_type="mobile air conditioning units",
        value=Decimal("0.1"),
        unit="fraction",
    )

    factors, observations, metrics = GlecNormalizer(Path("sources/glec/mappings.yaml")).normalize(
        (fuel,),
        (intensity,),
        refrigerants,
        (parameter,),
        raw=_raw(),
        version="3.2",
        parser_version="0.1.0",
    )

    assert len(factors) == 3
    assert len(observations) == 1
    assert metrics["excluded_missing_value"] == 1
    assert metrics["default_match_eligible"] == 2

    fuel_factor = factors[0]
    assert fuel_factor.factor_value == Decimal("0.0978")
    assert fuel_factor.factor_unit == "kgCO2e/MJ"
    assert fuel_factor.geographic_fit_type == GeographicFitType.CONTINENTAL
    assert fuel_factor.geographic_specificity == 1
    assert fuel_factor.methodology.details["source_ttw_g_co2e_per_mj"] == "75.3"

    intensity_factor = factors[1]
    assert intensity_factor.factor_value == Decimal("0.12")
    assert intensity_factor.factor_unit == "kgCO2e/tkm"
    assert intensity_factor.geographic_fit_type == GeographicFitType.COUNTRY_SPECIFIC
    assert intensity_factor.geographic_specificity == 3
    assert intensity_factor.methodology.details["source_wtt_value"] == "20"

    characterization = factors[2]
    assert characterization.entity_type == EnvironmentalEntityType.CHARACTERIZATION_RESULT
    assert characterization.intended_use == FactorIntendedUse.CHARACTERIZATION
    assert characterization.factor_value == Decimal("1530")
    assert observations[0].entity_type == EnvironmentalEntityType.CALCULATION_PARAMETER


def test_glec_parser_rejects_an_unreadable_pdf(tmp_path: Path) -> None:
    path = tmp_path / "invalid.pdf"
    path.write_bytes(b"not a PDF")

    with pytest.raises(PermanentIngestionError, match=r"not a readable v3\.2 PDF"):
        GlecParser().parse(path)


@pytest.mark.skipif(
    not os.getenv("ATLAS_GLEC_PDF"),
    reason="set ATLAS_GLEC_PDF to run the official GLEC v3.2 snapshot",
)
def test_official_glec_v3_2_snapshot() -> None:
    path = Path(os.environ["ATLAS_GLEC_PDF"])
    parser = GlecParser()
    parsed = parser.parse(path)
    factors, observations, metrics = GlecNormalizer(Path("sources/glec/mappings.yaml")).normalize(
        parsed.fuels,
        parsed.intensities,
        parsed.refrigerants,
        parsed.parameters,
        raw=_raw(),
        version=parsed.version,
        parser_version="0.1.0",
    )

    assert parser.metrics == {
        "parsed_rows": 528,
        "fuel_rows": 102,
        "transport_intensity_rows": 375,
        "refrigerant_rows": 45,
        "calculation_parameter_rows": 6,
    }
    assert len(factors) == 521
    assert len({factor.factor_id for factor in factors}) == 521
    assert len(observations) == 6
    assert metrics["characterization_factors"] == 44
