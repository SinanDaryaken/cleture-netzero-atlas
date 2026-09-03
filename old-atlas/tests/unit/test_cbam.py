from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from openpyxl import Workbook

from atlas.domain.enums import (
    EnvironmentalEntityType,
    FactorIntendedUse,
    GeographicFitType,
)
from atlas.domain.models import RawAssetReference
from sources.cbam.normalizer import CbamNormalizer
from sources.cbam.parser import CbamParser


def _default_workbook() -> bytes:
    workbook = Workbook()
    overview = workbook.active
    overview.title = "Overview"
    overview["A1"] = "Informational workbook; legally valid values in 2025/2621"
    history = workbook.create_sheet("Version History")
    history["A1"] = "Version 2 corrected by 2026/1740 on 2026-08-06"
    country = workbook.create_sheet("Türkiye")
    country.append(["Türkiye"])
    country.append(["Product CN Code", "Description", "Direct", "Indirect", "Total", "Route"])
    country.append(["Cement"])
    country.append(["2523 30 00", "Aluminous cement", "1,820", "0,140", "1,950", None])
    other = workbook.create_sheet("_Other Countries")
    other.append(["Other Countries and Territories"])
    other.append(["Product CN Code", "Description", "Direct", "Indirect", "Total", "Route"])
    other.append(["Cement"])
    other.append(["2523 10 00 90", "Grey clinker", "1,370", "0,050", "1,410", "(A)"])
    annex = workbook.create_sheet("Annex IV")
    annex.append(["Annex IV"])
    annex.append(["Product CN Code", "Description", "Highest default", "Route"])
    annex.append(["Cement"])
    annex.append(["2523 10 00 90", "Grey clinker", "1,440", "(A)"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _benchmark_workbook() -> bytes:
    workbook = Workbook()
    overview = workbook.active
    overview.title = "Overview"
    overview["A1"] = "Informational workbook; binding benchmarks in 2025/2620"
    history = workbook.create_sheet("Version history")
    history["A1"] = "Version 1"
    sheet = workbook.create_sheet("Benchmarks")
    sheet.append(["CN code", "Description", "Column A BMg*", "A route", "Column B BMg", "B route"])
    sheet.append(["Cement"])
    sheet.append([25231000, "Cement clinkers", 0.666, "(A)", 0.666, "(A)"])
    sheet.append([None, None, 0.859, "(B)(2)", 0.859, "(B)(2)"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _bundle(path: Path, default_content: bytes, benchmark_content: bytes) -> None:
    contents = {
        "default_values": ("cbam-default-values-definitive-2026-v2.xlsx", default_content),
        "benchmarks": ("cbam-benchmarks-definitive-2026-v1.xlsx", benchmark_content),
    }
    assets = [
        {
            "role": role,
            "filename": filename,
            "source_url": f"https://example.test/{filename}",
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        }
        for role, (filename, content) in contents.items()
    ]
    manifest = json.dumps(
        {"source": "CBAM", "dataset_version": "definitive-2026-v2", "assets": assets},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("bundle-manifest.json", manifest)
        for filename, content in contents.values():
            bundle.writestr(filename, content)


def _raw(path: Path) -> RawAssetReference:
    return RawAssetReference(
        bucket="atlas-raw",
        object_key="sources/cbam/test/bundle.zip",
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        filename=path.name,
        source_url="https://example.test/cbam",
        mime_type="application/zip",
        size_bytes=path.stat().st_size,
        downloaded_at=datetime.now(UTC),
        metadata={"acquisition_bundle": True},
    )


def test_cbam_bundle_preserves_regulatory_factor_and_benchmark_semantics(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cbam.zip"
    _bundle(path, _default_workbook(), _benchmark_workbook())
    parser = CbamParser()
    document = parser.parse(path)
    factors, observations, metrics = CbamNormalizer(
        Path("sources/cbam/mappings.yaml")
    ).normalize(
        document.default_values,
        document.benchmarks,
        raw=_raw(path),
        dataset_version="definitive-2026-v2",
        parser_version="0.1.0",
    )

    assert len(factors) == 3
    assert len(observations) == 4
    assert len({factor.factor_id for factor in factors}) == 3
    assert len({item.observation_id for item in observations}) == 4
    assert all(
        factor.entity_type == EnvironmentalEntityType.EMBODIED_EMISSION_FACTOR
        for factor in factors
    )
    assert all(factor.intended_use == FactorIntendedUse.CALCULATION_INPUT for factor in factors)
    assert all(factor.default_match_eligible is False for factor in factors)
    assert all(
        item.entity_type == EnvironmentalEntityType.CALCULATION_PARAMETER
        for item in observations
    )
    country = next(factor for factor in factors if factor.origin_geography.code == "TR")
    assert str(country.factor_value) == "1.950"
    assert country.factor_unit == "kgCO2e/kg"
    assert country.geographic_fit_type == GeographicFitType.COUNTRY_MODELLED
    assert country.methodology.details["markup_not_applied"] is True
    assert len(country.data_quality or "") <= 64
    proxies = [
        factor for factor in factors if factor.geographic_fit_type == GeographicFitType.PROXY
    ]
    assert len(proxies) == 2
    assert {factor.origin_geography.code for factor in proxies} == {
        "CBAM_OTHER",
        "CBAM_ANNEX_IV",
    }
    later = next(item for item in observations if item.attributes["production_route"] == "(B)(2)")
    assert later.attributes["valid_from_year"] == 2028
    assert later.attributes["valid_to_year"] == 2030
    assert metrics["default_match_eligible"] == 0


@pytest.mark.skipif(
    not (
        os.getenv("ATLAS_CBAM_DEFAULT_VALUES_XLSX")
        and os.getenv("ATLAS_CBAM_BENCHMARKS_XLSX")
    ),
    reason="set both ATLAS_CBAM workbook paths to run the official snapshot",
)
def test_official_cbam_definitive_2026_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "cbam-official.zip"
    _bundle(
        path,
        Path(os.environ["ATLAS_CBAM_DEFAULT_VALUES_XLSX"]).read_bytes(),
        Path(os.environ["ATLAS_CBAM_BENCHMARKS_XLSX"]).read_bytes(),
    )
    parser = CbamParser()
    document = parser.parse(path)
    factors, observations, metrics = CbamNormalizer(
        Path("sources/cbam/mappings.yaml")
    ).normalize(
        document.default_values,
        document.benchmarks,
        raw=_raw(path),
        dataset_version="definitive-2026-v2",
        parser_version="0.1.0",
    )

    assert len(document.default_values) == 11170
    assert len(document.benchmarks) == 2465
    assert len(factors) == 11170
    assert len(observations) == 2465
    assert len({factor.factor_id for factor in factors}) == 11170
    assert len({item.observation_id for item in observations}) == 2465
    assert metrics["country_modelled_factors"] == 10650
    assert metrics["proxy_factors"] == 520
    assert parser.metrics["benchmark_column_a"] == 661
    assert parser.metrics["benchmark_column_b"] == 1804
    assert parser.metrics["table_cement_factors"] == 345
    assert parser.metrics["table_fertilisers_factors"] == 2443
    assert parser.metrics["table_iron_steel_factors"] == 6629
    assert parser.metrics["table_aluminium_factors"] == 1656
    assert parser.metrics["table_hydrogen_factors"] == 97
