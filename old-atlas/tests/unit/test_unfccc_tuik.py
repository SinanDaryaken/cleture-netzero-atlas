from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

from atlas.domain.enums import EnvironmentalEntityType, FactorIntendedUse, FactorValueKind
from atlas.domain.models import RawAssetReference
from sources.unfccc_tuik.curator import UnfcccTuikCurator
from sources.unfccc_tuik.normalizer import UnfcccTuikNormalizer
from sources.unfccc_tuik.parser import UnfcccTuikParser, UnfcccTuikRow


def _submission_zip(path: Path, *, submission_year: int, reference_year: int) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Table1.A(a)s1"
    sheet.append(["TABLE 1.A(a)", None, None, None, None, None, None])
    sheet.append(["Fuel combustion", None, None, None, None, None, None])
    sheet.append([None] * 7)
    sheet.append([None] * 7)
    sheet.append([None] * 7)
    sheet.append(
        [
            "GREENHOUSE GAS SOURCE AND SINK CATEGORIES",
            "AGGREGATE ACTIVITY DATA",
            None,
            "IMPLIED EMISSION FACTORS",
            None,
            "EMISSIONS",
            None,
        ]
    )
    sheet.append([None, "Consumption", None, "CO2", "CH4", "CO2", "CH4"])
    sheet.append([None, "(TJ)", None, "(t/TJ)", "(kg/TJ)", "(kt)", "(kt)"])
    sheet.append([None] * 7)
    sheet.append(["1.A. Fuel combustion", 100, None, 55.2, 3.1, 5.52, 0.00031])
    sheet.append(["Gaseous fuels", 80, None, 56.0, 2.9, 4.48, 0.000232])
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    member = f"TUR_{submission_year}_{reference_year}_fixture.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(member, buffer.getvalue())


def test_crf_parser_separates_activity_ief_and_emission_result(tmp_path: Path) -> None:
    archive = tmp_path / "submission.zip"
    _submission_zip(archive, submission_year=2020, reference_year=2018)

    parser = UnfcccTuikParser()
    rows = parser.parse(
        archive,
        submission_year=2020,
        submission_status="submitted",
        schema_family="crf_legacy",
    )

    assert len(rows) == 10
    assert {row.entity_type for row in rows} == {
        EnvironmentalEntityType.ACTIVITY_DATA,
        EnvironmentalEntityType.IMPLIED_EMISSION_FACTOR,
        EnvironmentalEntityType.EMISSION_RESULT,
    }
    assert {row.reference_year for row in rows} == {2018}
    assert {row.submission_year for row in rows} == {2020}
    assert parser.metrics["workbook_members"] == 1


def test_normalizer_preserves_temporal_and_member_provenance(tmp_path: Path) -> None:
    archive = tmp_path / "submission.zip"
    _submission_zip(archive, submission_year=2020, reference_year=2018)
    rows = UnfcccTuikParser().parse(
        archive,
        submission_year=2020,
        submission_status="submitted",
        schema_family="crf_legacy",
    )
    raw = RawAssetReference(
        bucket="atlas-raw",
        object_key="sources/unfccc-tuik/raw.zip",
        sha256="a" * 64,
        filename="raw.zip",
        source_url="https://unfccc.int/resource/raw.zip",
        size_bytes=1,
        downloaded_at=datetime.now(UTC),
    )

    observations, factors, metrics = UnfcccTuikNormalizer(
        Path("sources/unfccc_tuik/mappings.yaml")
    ).normalize(rows, raw=raw, dataset_revision="b" * 64, parser_version="0.2.0")

    implied = next(
        observation
        for observation in observations
        if observation.entity_type == EnvironmentalEntityType.IMPLIED_EMISSION_FACTOR
    )
    assert implied.reference_year == 2018
    assert implied.attributes["submission_year"] == 2020
    assert implied.provenance.original_file == "TUR_2020_2018_fixture.xlsx"
    assert implied.provenance.file_checksum == rows[0].member_sha256
    assert len(factors) == 2
    assert factors[0].entity_type == EnvironmentalEntityType.EMISSION_FACTOR
    assert factors[0].factor_value_kind == FactorValueKind.CO2E_TOTAL
    assert factors[0].intended_use == FactorIntendedUse.INVENTORY
    assert factors[0].factor_unit == "kgCO2e/GJ"
    assert factors[0].factor_value == Decimal("55.2775")
    assert metrics["source_observations"] == 10
    assert metrics["default_match_eligible"] == 2


def test_curator_applies_ar5_and_stoichiometric_conversions() -> None:
    raw = RawAssetReference(
        bucket="atlas-raw",
        object_key="sources/unfccc-tuik/raw.zip",
        sha256="a" * 64,
        filename="raw.zip",
        source_url="https://unfccc.int/resource/raw.zip",
        size_bytes=1,
        downloaded_at=datetime.now(UTC),
    )

    def row(
        *,
        source_row: int,
        gas: str,
        value: str,
        unit: str,
        label: str | None = None,
        activity_unit: str | None = None,
        category_path: str | None = None,
    ) -> UnfcccTuikRow:
        return UnfcccTuikRow(
            submission_year=2025,
            submission_status="submitted",
            reference_year=2023,
            schema_family="crt_etf",
            entity_type=EnvironmentalEntityType.IMPLIED_EMISSION_FACTOR,
            category="1.A. Fuel combustion",
            category_path=category_path or f"1.A. Fuel combustion / row {source_row}",
            column_label=label or gas,
            gas=gas,
            value=Decimal(value),
            unit=unit,
            activity_unit=activity_unit,
            member_filename="TUR-CRT-2025-2023.xlsx",
            member_sha256="c" * 64,
            source_sheet="Table1.A(a)s1",
            source_row=source_row,
            source_column={"CO2": 5, "CH4": 6, "N2O": 7}[gas],
        )

    rows = (
        row(source_row=11, gas="CO2", value="55", unit="t/TJ"),
        row(source_row=11, gas="CH4", value="2", unit="kg/TJ"),
        row(source_row=11, gas="N2O", value="0.5", unit="kg/TJ"),
        row(
            source_row=12,
            gas="N2O",
            value="0.01",
            unit="source_unit_unspecified",
            label="kg N2O-N/kg N",
        ),
        row(
            source_row=13,
            gas="CO2",
            value="260",
            unit="kg/unit) (6",
            activity_unit="10^3m^3",
        ),
    )

    factors, metrics = UnfcccTuikCurator(
        {
            "1": "atlas.energy",
            "2": "atlas.industrial_processes",
            "3": "atlas.agriculture",
            "4": "atlas.agriculture.land_use",
            "5": "atlas.waste",
        },
        "0.2.0",
    ).curate(rows, raw=raw, dataset_revision="b" * 64, parser_version="0.3.0")

    by_unit = {factor.activity_unit: factor for factor in factors}
    assert by_unit["GJ"].factor_value == Decimal("55.1885")
    assert by_unit["GJ"].gases.ch4 == Decimal("0.002")
    assert by_unit["kg_nitrogen"].factor_value == (
        Decimal("0.01") * Decimal(44) / Decimal(28) * Decimal(265)
    )
    assert by_unit["m3"].factor_value == Decimal("0.26")
    assert metrics["curated_factors"] == 3

    duplicate_names = (
        row(
            source_row=21,
            gas="CO2",
            value="55",
            unit="t/TJ",
            category_path="1.A. Same reported category",
        ),
        row(
            source_row=22,
            gas="CO2",
            value="56",
            unit="t/TJ",
            category_path="1.A. Same reported category",
        ),
    )
    distinct_factors, _ = UnfcccTuikCurator(
        {"1": "atlas.energy"}, "0.2.0"
    ).curate(
        duplicate_names,
        raw=raw,
        dataset_revision="b" * 64,
        parser_version="0.3.0",
    )
    assert len({factor.source_factor_id for factor in distinct_factors}) == 2


def test_parser_repairs_shared_n2o_energy_unit() -> None:
    assert (
        UnfcccTuikParser._repair_inherited_ief_unit(
            entity_type=EnvironmentalEntityType.IMPLIED_EMISSION_FACTOR,
            gas="N2O",
            unit="t/TJ",
        )
        == "kg/TJ"
    )


def test_crt_member_reference_year_is_not_submission_year() -> None:
    filename = "TUR-CRT-2024-V0.1-2022-20241118-143948_started.xlsx"

    assert UnfcccTuikParser._reference_year(filename, 2024) == 2022
