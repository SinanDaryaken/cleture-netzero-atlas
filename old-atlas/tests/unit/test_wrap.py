from __future__ import annotations

import os
from pathlib import Path

import pytest
from openpyxl import Workbook

from atlas.domain.enums import (
    EnvironmentalEntityType,
    FactorIntendedUse,
    GeographicFitType,
    GeographyRole,
)
from atlas.domain.models import RawAssetReference
from sources.wrap.normalizer import WrapNormalizer
from sources.wrap.parser import WrapParser


def _fixture(path: Path) -> None:
    workbook = Workbook()
    hestia = workbook.active
    hestia.title = "emissions_database_hestia"
    hestia.append(
        [
            "source db",
            "impact type",
            "product",
            "year",
            "country",
            "production technology",
            "functional unit",
            "production stage",
            "intermediate product",
            "emission source",
            "impact",
            "model",
            "unit",
            "LSR category",
            "FLAG category",
            "value",
            "standard deviation",
            "aggregated quality",
            "created",
            "updated",
            "link",
        ]
    )
    hestia.append(
        [
            "HESTIA",
            "Aggregated",
            "Rice",
            "2010-2024",
            "India",
            "mixed",
            "1 kg",
            "Farm",
            None,
            None,
            "GWP100",
            "IPCC2021",
            "kg CO2e",
            None,
            None,
            2.5,
            0.4,
            2.2,
            None,
            None,
            "https://www.wrap.ngo/resources/guide/scope-3-ghg-measurement-and-reporting-protocols-food-and-drink",
        ]
    )
    hestia.append(
        [
            "HESTIA",
            "Aggregated",
            "Rice",
            "2010-2024",
            "India",
            "mixed",
            "1 kg",
            "Farm",
            None,
            None,
            "Eutrophication",
            "CML2001Baseline",
            "kg PO4-e",
            None,
            None,
            0.1,
            None,
            None,
            None,
            None,
            None,
        ]
    )
    refined = workbook.create_sheet("emissions_database_refined")
    refined.append(
        [
            "gpc_class",
            "gpc_brick",
            "gpc_classification",
            "source_db_name",
            "source_db_id",
            "lifecycle_stage",
            "origin_region",
            "applicable_region",
            "production_system",
            "factor_kg_co2e",
            "func_unit",
            "factor_type",
            "data_quality_score",
        ]
    )
    refined.append(
        [
            "Beer",
            None,
            "Beer",
            "Beer, regular",
            "foodsteps",
            "Packaging",
            "Multi-region",
            "UK",
            "mixed",
            0.2,
            "1 litre as purchased",
            "aggregate",
            2.7,
        ]
    )
    workbook.save(path)


def test_wrap_parser_selects_hestia_gwp100_and_curated_refined(tmp_path: Path) -> None:
    path = tmp_path / "wrap.xlsx"
    _fixture(path)

    parser = WrapParser()
    rows = parser.parse(path)

    assert len(rows) == 2
    assert parser.metrics["hestia_gwp100_rows"] == 1
    assert parser.metrics["refined_rows"] == 1
    assert rows[0].factor_kg_co2e == 2.5
    assert rows[1].functional_unit == "1 litre as purchased"


def test_wrap_normalizer_preserves_lca_and_geography_semantics(tmp_path: Path) -> None:
    path = tmp_path / "wrap.xlsx"
    _fixture(path)
    rows = WrapParser().parse(path)
    raw = RawAssetReference(
        bucket="atlas",
        object_key="sources/wrap/fixture/wrap.xlsx",
        sha256="a" * 64,
        filename="wrap.xlsx",
        source_url="https://www.wrap.ngo/sites/default/files/2024-03/WRAP-Emission-Factor-Database-v2.0.xlsx",
        size_bytes=path.stat().st_size,
        downloaded_at="2024-03-27T00:00:00Z",
    )

    factors, metrics = WrapNormalizer().normalize(
        rows, raw=raw, dataset_version="2.0", parser_version="0.1.0"
    )

    assert len(factors) == 2
    assert all(factor.entity_type == EnvironmentalEntityType.LCA_RESULT for factor in factors)
    assert all(factor.intended_use == FactorIntendedUse.CHARACTERIZATION for factor in factors)
    assert all(not factor.default_match_eligible for factor in factors)
    assert factors[0].geographic_fit_type == GeographicFitType.COUNTRY_MODELLED
    assert factors[1].geographic_fit_type == GeographicFitType.COUNTRY_MODELLED
    assert factors[0].activity_unit == "kg"
    assert factors[1].activity_unit == "L"
    assert [assignment.role for assignment in factors[0].geography_roles] == [
        GeographyRole.PRODUCTION_ORIGIN,
        GeographyRole.CALCULATION_APPLICABILITY,
    ]
    assert factors[0].geography_roles[0].geography.code == "IN"
    assert factors[0].geography_roles[1].geography.code == "IN"
    assert factors[1].geography_roles[0].geography.name == "Multi-region"
    assert factors[1].geography_roles[1].geography.code == "GB"
    assert metrics["default_match_eligible"] == 0


@pytest.mark.skipif(
    not os.getenv("ATLAS_WRAP_XLSX"),
    reason="set ATLAS_WRAP_XLSX to verify the official full snapshot",
)
def test_official_wrap_snapshot_contract() -> None:
    path = Path(os.environ["ATLAS_WRAP_XLSX"])

    parser = WrapParser()
    rows = parser.parse(path)

    assert len(rows) == 1140
    assert parser.metrics["hestia_gwp100_rows"] == 722
    assert parser.metrics["refined_rows"] == 418
    assert parser.metrics["negative_lca_results"] == 8
