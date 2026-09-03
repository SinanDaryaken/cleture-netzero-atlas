from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from openpyxl import Workbook

from atlas.domain.enums import ProvenanceRole
from atlas.domain.models import RawAssetReference
from atlas.infrastructure.http import HttpAssetFetcher
from sources.defra.normalizer import DefraNormalizer
from sources.defra.parser import DefraParser

HEADERS = (
    "ID",
    "Scope",
    "Level 1",
    "Level 2",
    "Level 3",
    "Level 4",
    "Column Text",
    "UOM",
    "GHG/Unit",
    "GHG Conversion Factor 2027",
)


async def test_defra_release_resolver_uses_requested_annual_page_flat_file() -> None:
    html = """
    <html><body>
      <a href="/files/summary.xlsx">Full conversion factors</a>
      <a href="/files/flat-2022.xlsx">Flat file (for automatic processing only)</a>
    </body></html>
    """
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=html))
    )
    fetcher = HttpAssetFetcher(client)

    asset_url, year = await fetcher.resolve_defra_release(
        "https://www.gov.uk/government/collections/archive",
        reference_year=2022,
        release_page=(
            "https://www.gov.uk/government/publications/"
            "greenhouse-gas-reporting-conversion-factors-2022"
        ),
    )
    await client.aclose()

    assert year == 2022
    assert asset_url == "https://www.gov.uk/files/flat-2022.xlsx"


def _workbook(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Factors by Category"
    sheet.append(["DEFRA fixture"])
    sheet.append(list(HEADERS))
    sheet.append(
        [
            "1_10_100_1_1",
            "Scope 1",
            "Fuels",
            "Diesel",
            None,
            None,
            None,
            "miles",
            "kg CO2e",
            1.609344,
        ]
    )
    sheet.append(
        [
            "1_10_100_1_2",
            "Scope 1",
            "Fuels",
            "Diesel",
            None,
            None,
            None,
            "miles",
            "kg CO2e of CO2 per unit",
            0.804672,
        ]
    )
    sheet.append(
        ["2_10_100_1_1", "Scope 1", "Fuels", "Blank", None, None, None, "litres", "kg CO2e", None]
    )
    sheet.append(
        ["3_10_100_1_5", "Scope 1", "Fuels", "Energy", None, None, None, "km", "kWh (Net CV)", 1]
    )
    sheet.append(
        [
            "4_10_100_1_2",
            "Scope 1",
            "Fuels",
            "Orphan",
            None,
            None,
            None,
            "litres",
            "kg CO2e of CO2 per unit",
            1,
        ]
    )
    workbook.save(path)


def _legacy_workbook(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Factors by Category"
    sheet.append(["DEFRA legacy fixture"])
    sheet.append(
        [
            "Scope",
            "Level 1",
            "Level 2",
            "Level 3",
            "Level 4",
            "Column Text",
            "UOM",
            "GHG",
            "Lookup",
            "GHG Conversion Factor 2020",
        ]
    )
    common = ["Scope 1", "Fuels", "Gaseous fuels", "Natural gas", None, "Volume"]
    sheet.append([*common, "cubic metres", "kg CO2e", "Natural gas cubic metres", 2.02])
    sheet.append([*common, "cubic metres", "kg CO2", "Natural gas cubic metres", 2.01])
    sheet.append([*common, "cubic metres", "kg CH4", "Natural gas cubic metres", "< 1"])
    workbook.save(path)


def test_defra_legacy_parser_generates_deterministic_semantic_identity(tmp_path: Path) -> None:
    workbook_path = tmp_path / "defra-2020.xlsx"
    _legacy_workbook(workbook_path)

    rows = DefraParser().parse(workbook_path)

    assert len(rows) == 3
    assert len({row.base_source_id for row in rows}) == 1
    assert len({row.logical_key for row in rows}) == 1
    assert all(row.source_id.startswith("legacy_") for row in rows)
    assert rows[-1].value is None
    assert rows[-1].value_qualifier == "< 1"


def test_defra_parser_and_normalizer_preserve_nulls_and_provenance(tmp_path: Path) -> None:
    workbook_path = tmp_path / "defra.xlsx"
    _workbook(workbook_path)
    rows = DefraParser().parse(workbook_path)
    raw = RawAssetReference(
        bucket="atlas-raw",
        object_key="sources/defra/test/defra.xlsx",
        sha256="a" * 64,
        filename="defra.xlsx",
        source_url="https://example.test/defra.xlsx",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        size_bytes=workbook_path.stat().st_size,
        downloaded_at=datetime.now(UTC),
    )

    factors, metrics = DefraNormalizer(Path("sources/defra/mappings.yaml")).normalize(
        rows,
        raw=raw,
        release_year=2027,
        parser_version="1.0.0",
    )

    assert len(rows) == 5
    assert len(factors) == 1
    factor = factors[0]
    assert factor.factor_value == Decimal("1")
    assert factor.gases.co2 == Decimal("0.5")
    assert factor.factor_unit == "kgCO2e/km"
    assert factor.origin_geography.code == "GB"
    assert [geography.code for geography in factor.applicable_geographies] == ["GB"]
    assert factor.provenance.role == ProvenanceRole.TOTAL
    assert factor.provenance.row == 3
    assert factor.component_provenance[0].role == ProvenanceRole.CO2
    assert factor.component_provenance[0].row == 4
    assert metrics == {
        "parsed_rows": 5,
        "normalized_factors": 1,
        "missing_total_values": 1,
        "conversion_only_rows": 1,
        "orphan_component_rows": 1,
        "excluded_rows": 3,
    }
