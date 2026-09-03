from __future__ import annotations

import io
import os
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from openpyxl import Workbook

from atlas.domain.enums import FactorIntendedUse, FactorValueKind, GeographicFitType
from atlas.domain.models import PipelineContext, PipelineRun, RawAssetReference
from atlas.infrastructure.http import HttpAssetFetcher
from atlas.ingestion.base import BaseAtlasSourceAdapter
from atlas.ingestion.registry import SourceRegistry
from atlas.validation import QualityEngine
from sources.ipcc.adapter import IpccAdapter
from sources.ipcc.normalizer import IpccNormalizer
from sources.ipcc.parser import EXPECTED_HEADERS, IpccParser, IpccRow


def _workbook(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(EXPECTED_HEADERS)
    sheet.append(
        (
            "1001",
            None,
            "1.A - Fuel Combustion Activities",
            "CARBON DIOXIDE",
            None,
            "Natural Gas",
            None,
            "2006 IPCC default",
            "CO2 Emission Factor",
            "Boiler",
            "Dry gas",
            None,
            None,
            None,
            "56100.123456789012345678",
            "kg/TJ",
            "EF * fuel consumption",
            "Worksheet 1.A",
            "IPCC 2006 Guidelines",
            "IPCC 2006 Volume 2",
            "IPCC",
        )
    )
    sheet.append(
        (
            "1002",
            None,
            "1.A - Fuel Combustion Activities",
            "CARBON DIOXIDE",
            None,
            "Natural Gas",
            None,
            "2019 Refinement default",
            "Net Calorific Value",
            None,
            None,
            None,
            None,
            None,
            "43.0",
            "TJ/kt",
            "Activity * NCV * EF",
            "Worksheet 1.A",
            "2019 Refinement",
            "2019 Refinement Volume 2",
            "IPCC TFI TSU",
        )
    )
    sheet.append(
        (
            "1003",
            None,
            "1.A - Fuel Combustion Activities",
            "METHANE",
            None,
            "Natural Gas",
            None,
            "2006 IPCC default",
            "CH4 Emission Factor",
            None,
            None,
            "Turkey",
            None,
            None,
            "1.0",
            "kg/TJ",
            None,
            None,
            None,
            "IPCC 2006 Guidelines",
            "IPCC",
        )
    )
    sheet.append(
        (
            "1004",
            None,
            "1.A - Fuel Combustion Activities",
            "METHANE",
            None,
            "Natural Gas",
            None,
            "Measured",
            "CH4 Emission Factor",
            None,
            None,
            None,
            None,
            None,
            "2.0",
            "kg/TJ",
            None,
            None,
            None,
            "Journal",
            "Researcher",
        )
    )
    sheet.append(
        (
            "1005",
            None,
            "4.A - Solid Waste Disposal",
            "METHANE",
            None,
            None,
            None,
            "2006 IPCC default",
            "Methane Correction Factor",
            None,
            None,
            None,
            None,
            None,
            "0.4 (0.2-0.5)",
            "fraction",
            None,
            None,
            None,
            "IPCC 2006 Guidelines",
            "IPCC",
        )
    )
    workbook.save(path)


def _raw(path: Path) -> RawAssetReference:
    return RawAssetReference(
        bucket="atlas-raw",
        object_key="sources/ipcc/efdb/test/ipcc.xlsx",
        sha256="c" * 64,
        filename="ipcc.xlsx",
        source_url="https://www.ipcc-nggip.iges.or.jp/EFDB/find_ef_xls.php",
        size_bytes=path.stat().st_size,
        downloaded_at=datetime.now(UTC),
    )


def test_ipcc_defaults_preserve_factor_and_calculation_parameter_semantics(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ipcc-export.xls"
    _workbook(path)
    parser = IpccParser()
    rows = parser.parse(path)
    factors, metrics = IpccNormalizer(Path("sources/ipcc/mappings.yaml")).normalize(
        rows,
        raw=_raw(path),
        dataset_revision="d" * 64,
        parser_version="0.1.0",
    )

    assert len(rows) == 5
    assert len(factors) == 2
    assert metrics["excluded_non_default"] == 1
    assert metrics["excluded_unmapped_geography"] == 1
    assert metrics["excluded_non_numeric"] == 1

    emission_factor = next(
        factor for factor in factors if factor.source_factor_id == "ipcc:efdb:1001"
    )
    assert emission_factor.factor_value_kind == FactorValueKind.CO2_ONLY
    assert emission_factor.intended_use == FactorIntendedUse.INVENTORY
    assert emission_factor.factor_unit == "kg/TJ"
    assert emission_factor.activity_unit == "TJ"
    assert emission_factor.factor_value.as_tuple().exponent == -18
    assert emission_factor.geographic_fit_type == GeographicFitType.GLOBAL
    assert emission_factor.default_match_eligible is False

    parameter = next(factor for factor in factors if factor.source_factor_id == "ipcc:efdb:1002")
    assert parameter.factor_value_kind == FactorValueKind.CALCULATION_PARAMETER
    assert parameter.intended_use == FactorIntendedUse.CALCULATION_INPUT
    assert parameter.methodology.details["parameter_role"] == "calculation_input"
    assert parameter.methodology.details["equation"] == "Activity * NCV * EF"
    assert not QualityEngine().validate((parameter,)).requires_review


def _component_row(
    ef_id: str,
    *,
    gas: str,
    fuel: str,
    value: str,
    unit: str,
    source_row: int,
) -> IpccRow:
    return IpccRow(
        ef_id=ef_id,
        category_2006="1.A.1 - Energy Industries",
        gas=gas,
        fuel_2006=fuel,
        parameter_type="2006 IPCC default",
        description=f"{gas} Emission Factor",
        raw_value=value,
        value=value,
        unit=unit,
        source_row=source_row,
    )


def test_ipcc_builds_traceable_canonical_co2e_for_complete_fuel_groups(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ipcc-export.xls"
    _workbook(path)
    rows = (
        _component_row(
            "ng-co2",
            gas="CARBON DIOXIDE",
            fuel="Natural Gas",
            value="56.1",
            unit="t/TJ",
            source_row=10,
        ),
        _component_row(
            "ng-ch4", gas="METHANE", fuel="Natural Gas", value="1", unit="kg/TJ", source_row=11
        ),
        _component_row(
            "ng-n2o",
            gas="NITROUS OXIDE",
            fuel="Natural Gas",
            value="0.1",
            unit="kg/TJ",
            source_row=12,
        ),
        _component_row(
            "diesel-co2",
            gas="CARBON DIOXIDE",
            fuel="Diesel Oil",
            value="74.1",
            unit="t/TJ",
            source_row=20,
        ),
        _component_row(
            "diesel-ch4", gas="METHANE", fuel="Diesel Oil", value="3", unit="kg/TJ", source_row=21
        ),
        _component_row(
            "diesel-n2o",
            gas="NITROUS OXIDE",
            fuel="Diesel Oil",
            value="0.6",
            unit="kg/TJ",
            source_row=22,
        ),
    )

    factors, metrics = IpccNormalizer(Path("sources/ipcc/mappings.yaml")).normalize(
        rows,
        raw=_raw(path),
        dataset_revision="e" * 64,
        parser_version="0.1.0",
    )

    totals = [factor for factor in factors if factor.default_match_eligible]
    assert len(totals) == 2
    assert metrics["canonical_co2e_totals"] == 2
    assert metrics["default_match_eligible"] == 2
    natural_gas = next(factor for factor in totals if "Natural Gas" in factor.name)
    assert natural_gas.factor_value == Decimal("56.1545")
    assert natural_gas.factor_unit == "kgCO2e/GJ"
    assert natural_gas.activity_unit == "GJ"
    assert natural_gas.methodology.scope == "scope_1"
    assert natural_gas.methodology.details["derivation"]["source_reported_total"] is False
    assert {item.role.value for item in natural_gas.component_provenance} == {
        "co2",
        "ch4",
        "n2o",
    }


def test_ipcc_does_not_invent_total_for_incomplete_or_ambiguous_group(tmp_path: Path) -> None:
    path = tmp_path / "ipcc-export.xls"
    _workbook(path)
    rows = (
        _component_row(
            "co2",
            gas="CARBON DIOXIDE",
            fuel="Natural Gas",
            value="56.1",
            unit="t/TJ",
            source_row=10,
        ),
        _component_row(
            "ch4-a", gas="METHANE", fuel="Natural Gas", value="1", unit="kg/TJ", source_row=11
        ),
        _component_row(
            "ch4-b", gas="METHANE", fuel="Natural Gas", value="2", unit="kg/TJ", source_row=12
        ),
        _component_row(
            "n2o", gas="NITROUS OXIDE", fuel="Natural Gas", value="0.1", unit="kg/TJ", source_row=13
        ),
        _component_row(
            "coal-co2", gas="CARBON DIOXIDE", fuel="Coal", value="94.6", unit="t/TJ", source_row=20
        ),
    )

    factors, metrics = IpccNormalizer(Path("sources/ipcc/mappings.yaml")).normalize(
        rows,
        raw=_raw(path),
        dataset_revision="f" * 64,
        parser_version="0.1.0",
    )

    assert not any(factor.default_match_eligible for factor in factors)
    assert metrics["composite_groups_ambiguous"] == 1
    assert metrics["composite_groups_incomplete"] == 1


def test_ipcc_semantic_revision_ignores_volatile_package_metadata() -> None:
    def package(core: str) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as workbook:
            workbook.writestr("docProps/core.xml", core)
            workbook.writestr("xl/worksheets/sheet1.xml", "<sheet><value>42</value></sheet>")
        return buffer.getvalue()

    assert HttpAssetFetcher._xlsx_sheet_revision(
        package("created-at-one")
    ) == HttpAssetFetcher._xlsx_sheet_revision(package("created-at-two"))


async def test_ipcc_adapter_can_acquire_verified_local_snapshot(tmp_path: Path) -> None:
    root = tmp_path / "source-assets"
    snapshot = root / "ipcc" / "ipcc-efdb.xlsx"
    snapshot.parent.mkdir(parents=True)
    _workbook(snapshot)
    repository = cast(Any, type("Repository", (), {})())
    repository.last_source_revision = AsyncMock(return_value=None)
    repository.record_source_check = AsyncMock()
    source = SourceRegistry.discover(Path("sources")).get("IPCC")
    adapter = IpccAdapter(
        repository=repository,
        storage=cast(Any, object()),
        local_asset_root=root,
    )
    context = PipelineContext(source=source, run=PipelineRun(source_code="IPCC"))

    result = await adapter.check(context)
    asset = await adapter.fetch(context)

    assert result.changed is True
    assert context.metrics["reported_rows"] == 5
    assert asset.local_path is not None and asset.local_path.is_file()
    assert asset.metadata["acquisition"] == "local_source_asset_root"
    await adapter.close()


async def test_ipcc_unknown_commercial_api_rights_require_review() -> None:
    source = SourceRegistry.discover(Path("sources")).get("IPCC")
    source = source.model_copy(
        update={
            "quality": source.quality.model_copy(
                update={"minimum_expected_rows": None, "minimum_expected_factors": None}
            )
        }
    )
    adapter = BaseAtlasSourceAdapter(
        repository=cast(Any, object()),
        storage=cast(Any, object()),
    )
    report = await adapter.validate(
        PipelineContext(source=source, run=PipelineRun(source_code="IPCC"))
    )

    assert any(
        finding.rule_code == "license.api_distribution_unapproved" for finding in report.findings
    )
    assert report.requires_review


@pytest.mark.skipif(
    not os.getenv("ATLAS_IPCC_EXPORT"),
    reason="set ATLAS_IPCC_EXPORT to run the official EFDB export snapshot",
)
def test_official_ipcc_export_snapshot() -> None:
    path = Path(os.environ["ATLAS_IPCC_EXPORT"])
    parser = IpccParser()
    rows = parser.parse(path)
    revision = HttpAssetFetcher._xlsx_sheet_revision(path.read_bytes())
    factors, metrics = IpccNormalizer(Path("sources/ipcc/mappings.yaml")).normalize(
        rows,
        raw=_raw(path),
        dataset_revision=revision,
        parser_version="0.1.0",
    )

    assert len(rows) == 27566
    assert len(factors) == 8235
    assert metrics["canonical_co2e_totals"] == 217
    assert metrics["default_match_eligible"] == 217
    assert any(
        factor.name.startswith("IPCC AR5 CO₂e combustion factor — Natural Gas —")
        for factor in factors
    )
    assert metrics["excluded_unmapped_geography"] > 10000
