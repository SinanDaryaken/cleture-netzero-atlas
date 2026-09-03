# ruff: noqa: RUF001 -- fixtures intentionally preserve official Turkish labels.

from __future__ import annotations

import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from atlas.domain.enums import FactorValueKind, GeographicFitType
from atlas.domain.models import CanonicalFactor, RawAssetReference
from atlas.ingestion.errors import PermanentIngestionError
from atlas.validation import QualityEngine
from sources.etkb.normalizer import EtkbNormalizer
from sources.etkb.parser import EtkbParser, EtkbRow


def _raw(year: int = 2023) -> RawAssetReference:
    return RawAssetReference(
        bucket="atlas-raw",
        object_key=f"sources/etkb/{year}/test.pdf",
        sha256=str(year % 10) * 64,
        filename=f"etkb-electricity-{year}.pdf",
        source_url=f"https://example.test/etkb-{year}.pdf",
        size_bytes=123,
        downloaded_at=datetime.now(UTC),
    )


def test_etkb_normalizer_keeps_publisher_co2_and_co2e_values_separate() -> None:
    row = EtkbRow(
        reference_year=2023,
        category="consumption_point",
        activity_key="consumption_distribution",
        activity_name="Dağıtım Hattından Bağlı Tüketim Noktası",
        co2_t_per_mwh=Decimal("0.465"),
        co2e_t_per_mwh=Decimal("0.469"),
        source_page=2,
        source_table="Elektrik Tüketim Noktası Emisyon Faktörleri",
        source_row=3,
        co2_column=3,
        co2e_column=4,
    )

    factors, metrics = EtkbNormalizer(Path("sources/etkb/mappings.yaml")).normalize(
        (row,),
        raw=_raw(),
        release_year=2023,
        calculation_revision="00",
        parser_version="0.1.0",
    )

    co2, co2e = factors
    assert co2.factor_value == Decimal("0.465")
    assert co2.factor_unit == "kgCO2/kWh"
    assert co2.factor_value_kind == FactorValueKind.CO2_ONLY
    assert co2.default_match_eligible is False
    assert co2e.factor_value == Decimal("0.469")
    assert co2e.factor_unit == "kgCO2e/kWh"
    assert co2e.factor_value_kind == FactorValueKind.CO2E_TOTAL
    assert co2e.default_match_eligible is True
    assert co2e.geographic_fit_type == GeographicFitType.COUNTRY_SPECIFIC
    assert co2e.origin_geography is not None
    assert co2e.origin_geography.code == "TR"
    assert metrics["normalized_factors"] == 2
    assert metrics["default_match_eligible"] == 1
    assert QualityEngine().validate(factors).findings == ()


def test_etkb_parser_rejects_an_unreadable_pdf(tmp_path: Path) -> None:
    path = tmp_path / "invalid.pdf"
    path.write_bytes(b"not a PDF")

    with pytest.raises(PermanentIngestionError, match="not a readable annual PDF"):
        EtkbParser().parse(path)


@pytest.mark.skipif(
    not os.getenv("ATLAS_ETKB_PDF_DIR"),
    reason="set ATLAS_ETKB_PDF_DIR to run the official ETKB annual PDF snapshots",
)
def test_official_etkb_annual_snapshots() -> None:
    directory = Path(os.environ["ATLAS_ETKB_PDF_DIR"])
    expected = {
        2020: (date(2024, 3, 18), "01", Decimal("0.420"), Decimal("0.462")),
        2021: (date(2024, 3, 18), "00", Decimal("0.439"), Decimal("0.479")),
        2022: (date(2024, 12, 6), "00", Decimal("0.442"), Decimal("0.478")),
        2023: (date(2025, 12, 26), "00", Decimal("0.434"), Decimal("0.469")),
    }
    all_factors: list[CanonicalFactor] = []
    for year, (published_on, revision, national_co2e, distribution_co2e) in expected.items():
        parser = EtkbParser()
        document = parser.parse(directory / f"{year}.pdf")
        factors, metrics = EtkbNormalizer(Path("sources/etkb/mappings.yaml")).normalize(
            document.rows,
            raw=_raw(year),
            release_year=year,
            calculation_revision=document.calculation_revision,
            parser_version="0.1.0",
        )
        assert document.reference_year == year
        assert document.published_on == published_on
        assert document.calculation_revision == revision
        assert len(document.rows) == 10
        assert parser.metrics["parsed_rows"] == 10
        assert len(factors) == 20
        assert metrics["co2_only_factors"] == 10
        assert metrics["co2e_total_factors"] == 10
        assert metrics["default_match_eligible"] == 10
        assert next(
            factor.factor_value
            for factor in factors
            if factor.logical_factor_id.endswith("turkiye_gross_generation:co2e")
        ) == national_co2e
        assert next(
            factor.factor_value
            for factor in factors
            if factor.logical_factor_id.endswith("consumption_distribution:co2e")
        ) == distribution_co2e
        assert QualityEngine().validate(factors).findings == ()
        all_factors.extend(factors)

    assert len(all_factors) == 80
    assert len({factor.factor_id for factor in all_factors}) == 80
    assert len({factor.logical_factor_id for factor in all_factors}) == 20
