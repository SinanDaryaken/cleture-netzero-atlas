from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from atlas.domain.enums import (
    EnvironmentalEntityType,
    FactorIntendedUse,
    FactorValueKind,
    GeographicFitType,
)
from atlas.domain.models import RawAssetReference
from atlas.validation import QualityEngine
from sources.oekobaudat.normalizer import OekobaudatNormalizer
from sources.oekobaudat.parser import OekobaudatParser

HEADERS = (
    "UUID",
    "Version",
    "Name (de)",
    "Name (en)",
    "Kategorie (original)",
    "Kategorie (en)",
    "Konformitaet",
    "Hintergrunddatenbank(en)",
    "Laenderkennung",
    "Typ",
    "Referenzjahr",
    "Gueltig bis",
    "URL",
    "Declaration owner",
    "Veroeffentlicht am",
    "Registrierungsnummer",
    "Registrierungsstelle",
    "UUID des Vorgaengers",
    "Version des Vorgaengers",
    "Bezugsgroesse",
    "Bezugseinheit",
    "Referenzfluss-UUID",
    "Referenzfluss-Name",
    "Modul",
    "Szenario",
    "Szenariobeschreibung",
    "GWP",
    "GWPtotal (A2)",
    "GWPbiogenic (A2)",
    "GWPfossil (A2)",
    "GWPluluc (A2)",
)


def _write_fixture(path: Path) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=HEADERS, delimiter=";")
    writer.writeheader()
    base = {
        "UUID": "c93da4c3-94c9-4c86-b092-610cf1cf012f",
        "Version": "00.10.000",
        "Name (de)": "Dämmstoffplatte",
        "Name (en)": "Insulation board",
        "Kategorie (original)": "Dämmstoffe / Platten",
        "Kategorie (en)": "Insulation materials / Panels",
        "Konformitaet": "EN 15804+A2 / ISO 14025",
        "Hintergrunddatenbank(en)": "Sphera MLC",
        "Laenderkennung": "DE",
        "Typ": "specific dataset",
        "Referenzjahr": "2021",
        "Gueltig bis": "2026",
        "URL": "https://www.oekobaudat.de/process/test",
        "Declaration owner": "Example owner",
        "Veroeffentlicht am": "2021-03-15",
        "Registrierungsnummer": "EPD-TEST",
        "Registrierungsstelle": "Test body",
        "UUID des Vorgaengers": "",
        "Version des Vorgaengers": "",
        "Bezugsgroesse": "1000",
        "Bezugseinheit": "kg",
        "Referenzfluss-UUID": "adeac8dc-45df-5c2f-dbd1-2914b76fbffc",
        "Referenzfluss-Name": "1000 kg insulation board",
        "Modul": "A1-A3",
        "Szenario": "",
        "Szenariobeschreibung": "",
        "GWP": "",
        "GWPtotal (A2)": "1250",
        "GWPbiogenic (A2)": "-20",
        "GWPfossil (A2)": "1269",
        "GWPluluc (A2)": "1",
    }
    writer.writerow(base)
    writer.writerow(
        {
            **base,
            "Modul": "D",
            "Laenderkennung": "EU",
            "Bezugsgroesse": "1",
            "GWPtotal (A2)": "-8.5",
        }
    )
    writer.writerow(
        {
            **base,
            "UUID": "0f078421-3f8c-4b82-96df-0bdbee25c776",
            "Version": "00.01.000",
            "Modul": "A1-A3",
            "Laenderkennung": "GLO",
            "Bezugsgroesse": "1",
            "GWP": "2.4",
            "GWPtotal (A2)": "",
            "GWPbiogenic (A2)": "",
            "GWPfossil (A2)": "",
            "GWPluluc (A2)": "",
            "Konformitaet": "EN 15804+A1 / ISO 14025",
        }
    )
    writer.writerow({**base, "Modul": "A4", "GWPtotal (A2)": ""})
    path.write_bytes(buffer.getvalue().encode("iso-8859-1"))


def test_oekobaudat_preserves_module_gwp_lca_semantics(tmp_path: Path) -> None:
    path = tmp_path / "oekobaudat.csv"
    _write_fixture(path)
    parser = OekobaudatParser()
    rows = parser.parse(path)

    assert len(rows) == 3
    assert parser.metrics == {
        "input_rows": 4,
        "parsed_rows": 3,
        "excluded_missing_total_gwp": 1,
        "excluded_missing_reference": 0,
        "a1_gwp_rows": 1,
        "a2_gwp_rows": 2,
        "datasets_with_gwp": 2,
    }
    raw = RawAssetReference(
        bucket="atlas-raw",
        object_key="sources/oekobaudat/fixture/export.csv",
        sha256="a" * 64,
        filename="export.csv",
        source_url="https://www.oekobaudat.de/en/service/downloads.html",
        mime_type="text/csv",
        size_bytes=path.stat().st_size,
        downloaded_at=datetime.now(UTC),
    )
    factors, metrics = OekobaudatNormalizer(
        Path("sources/oekobaudat/mappings.yaml")
    ).normalize(
        rows,
        raw=raw,
        dataset_version="2024-II",
        parser_version="0.1.0",
    )

    assert len(factors) == 3
    assert metrics["a1_gwp_factors"] == 1
    assert metrics["a2_gwp_factors"] == 2
    assert metrics["negative_lca_results"] == 1
    assert metrics["default_match_eligible"] == 0
    assert all(factor.entity_type == EnvironmentalEntityType.LCA_RESULT for factor in factors)
    assert all(factor.factor_value_kind == FactorValueKind.CO2E_TOTAL for factor in factors)
    assert all(factor.intended_use == FactorIntendedUse.CHARACTERIZATION for factor in factors)
    assert all(factor.default_match_eligible is False for factor in factors)
    assert factors[0].factor_value == Decimal("1.25")
    assert factors[0].activity_unit == "kg"
    assert factors[0].methodology.details["original_reference_quantity"] == "1000"
    assert factors[1].geographic_fit_type == GeographicFitType.CONTINENTAL
    assert factors[2].geographic_fit_type == GeographicFitType.GLOBAL
    negative = next(factor for factor in factors if factor.factor_value < 0)
    assert not any(
        finding.rule_code == "factor.negative_value"
        for finding in QualityEngine().validate((negative,)).findings
    )
