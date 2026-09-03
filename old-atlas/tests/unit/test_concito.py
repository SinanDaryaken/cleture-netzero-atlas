from __future__ import annotations

import zipfile
from decimal import Decimal
from pathlib import Path

from atlas.domain.enums import EnvironmentalEntityType, FactorIntendedUse, GeographyRole
from atlas.domain.models import RawAssetReference
from sources.concito.normalizer import ConcitoNormalizer
from sources.concito.parser import ConcitoParser


def _bundle(path: Path) -> None:
    index = b"""
    <table><thead><tr>
      <th>Product Name (t CO2e/t)</th><th>Country</th><th>Category</th>
      <th>Total</th><th>Agriculture</th><th>ILUC</th><th>Processing</th>
      <th>Packaging</th><th>Transport</th><th>Retail</th><th>Id</th>
    </tr></thead><tbody><tr>
      <td>Test food</td><td>DK</td><td>Prepared foods</td><td>1.100</td>
      <td>1.000</td><td>-0.100</td><td>0.000</td><td>0.100</td>
      <td>0.090</td><td>0.010</td><td>Ra99999-DK</td>
    </tr></tbody></table>
    """
    detail = b"""
    <table><tbody>
      <tr><th>Product Name</th><td>Test food</td></tr>
      <tr><th>Country</th><td>DK</td></tr>
      <tr><th>Category</th><td>Prepared foods</td></tr>
      <tr><th>Total (t CO2e/t)</th><td>1.100001</td></tr>
      <tr><th>Agriculture (t CO2e/t)</th><td>1.000001</td></tr>
      <tr><th>Packaging (t CO2e/t)</th><td>0.100001</td></tr>
      <tr><th>ILUC (t CO2e/t)</th><td>-0.100001</td></tr>
      <tr><th>Retail (t CO2e/t)</th><td>0.010001</td></tr>
      <tr><th>Transport (t CO2e/t)</th><td>0.090001</td></tr>
      <tr><th>Other (t CO2e/t)</th><td>0.000000</td></tr>
      <tr><th>ID</th><td>Ra99999-DK</td></tr>
    </tbody></table>
    """
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("index.html", index)
        archive.writestr("activities/Ra99999-DK.html", detail)


def test_concito_parser_uses_full_precision_detail_pages(tmp_path: Path) -> None:
    path = tmp_path / "concito.zip"
    _bundle(path)
    parser = ConcitoParser(
        expected_activities=1,
        expected_country_counts={"DK": 1, "ES": 0, "FR": 0, "GB": 0, "NL": 0},
    )

    rows = parser.parse(path)

    assert len(rows) == 7
    assert rows[0].factor_tco2e_per_t == Decimal("1.100001")
    assert {row.lifecycle_stage for row in rows} == {
        "Total",
        "Agriculture",
        "ILUC",
        "Processing",
        "Packaging",
        "Transport",
        "Retail",
    }
    assert parser.metrics["zero_component_rows"] == 1
    assert parser.metrics["negative_lca_results"] == 1


def test_concito_normalizer_excludes_zero_components_and_preserves_lca(tmp_path: Path) -> None:
    path = tmp_path / "concito.zip"
    _bundle(path)
    rows = ConcitoParser(
        expected_activities=1,
        expected_country_counts={"DK": 1, "ES": 0, "FR": 0, "GB": 0, "NL": 0},
    ).parse(path)
    raw = RawAssetReference(
        bucket="atlas",
        object_key="sources/concito/fixture/concito.zip",
        sha256="b" * 64,
        filename="concito.zip",
        source_url="https://www.thebigclimatedatabase.com/",
        size_bytes=path.stat().st_size,
        downloaded_at="2024-09-23T00:00:00Z",
    )

    factors, metrics = ConcitoNormalizer().normalize(
        rows, raw=raw, dataset_version="1.2", parser_version="0.1.0"
    )

    assert len(factors) == 6
    assert metrics["excluded_zero_components"] == 1
    assert all(factor.entity_type == EnvironmentalEntityType.LCA_RESULT for factor in factors)
    assert all(factor.intended_use == FactorIntendedUse.CHARACTERIZATION for factor in factors)
    assert all(not factor.default_match_eligible for factor in factors)
    assert all(factor.activity_unit == "kg" for factor in factors)
    assert all(factor.factor_unit == "kgCO2e/kg" for factor in factors)
    assert factors[0].applicable_geographies[0].code == "DK"
    assert factors[0].origin_geography is None
    assert factors[0].geography_roles[0].role == GeographyRole.MARKET
    assert factors[0].geography_roles[0].geography.code == "DK"
    assert factors[0].geography_roles[0].source_field == "Country"
