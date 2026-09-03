from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from atlas.domain.enums import EnvironmentalEntityType, FactorIntendedUse
from atlas.domain.models import RawAssetReference
from sources.plastics_europe.normalizer import PlasticsEuropeNormalizer
from sources.plastics_europe.parser import (
    PackageSpec,
    PlasticsEuropeParser,
    ReportSpec,
)


def _process(process_uuid: str, key: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <processDataSet xmlns="http://lca.jrc.it/ILCD/Process"
      xmlns:vellum="https://vellum.cauldron.ch">
      <processInformation><dataSetInformation>
        <UUID>{process_uuid}</UUID><name><baseName>1kg product--{key}--EUROPE</baseName></name>
      </dataSetInformation><quantitativeReference>
        <referenceToReferenceFlow>0</referenceToReferenceFlow>
      </quantitativeReference></processInformation>
      <exchanges><exchange dataSetInternalID="0" vellum:unitName="kg">
        <meanAmount>1.0</meanAmount><generalComment>is reference product</generalComment>
      </exchange></exchanges>
    </processDataSet>""".encode()


def _bundle(path: Path) -> PackageSpec:
    spec = PackageSpec(
        key="fixture",
        filename="Fixture.zip",
        family="Fixture polymers",
        reference_year=2024,
        valid_from=date(2024, 1, 1),
        valid_to=date(2029, 12, 31),
        reports=(ReportSpec("Fixture.pdf", ("HDPE", "PP")),),
    )
    package_buffer = io.BytesIO()
    with zipfile.ZipFile(package_buffer, "w") as package:
        package.writestr("Fixture/HDPE.xml", _process("process-hdpe", "HDPE"))
        package.writestr("Fixture/PP.xml", _process("process-pp", "PP"))
        package.writestr("Fixture/Fixture.pdf", b"fixture pdf")
    package_content = package_buffer.getvalue()
    package_sha = hashlib.sha256(package_content).hexdigest()
    manifest = {
        "packages": {
            "fixture": {
                "filename": "Fixture.zip",
                "url": "https://example.test/Fixture.zip",
                "sha256": package_sha,
            }
        }
    }
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("bundle-manifest.json", json.dumps(manifest))
        bundle.writestr("packages/Fixture.zip", package_content)
    return spec


def _pages(_: bytes) -> tuple[str, ...]:
    return (
        "LCIA Results\nImpact Category Unit HDPE PP\n"
        "Climate change kg CO 2 eq 2.16 1.92",
    )


def test_plastics_europe_parser_links_pdf_gwp_to_ilcd_reference_flow(
    tmp_path: Path,
) -> None:
    path = tmp_path / "plastics-europe.zip"
    spec = _bundle(path)
    parser = PlasticsEuropeParser(packages=(spec,), pdf_text_extractor=_pages)

    rows = parser.parse(path)

    assert len(rows) == 2
    assert rows[0].process_uuid == "process-hdpe"
    assert rows[0].gwp100_kgco2e == Decimal("2.16")
    assert rows[1].product_name == "Polypropylene resin (PP)"
    assert rows[1].gwp100_kgco2e == Decimal("1.92")
    assert all(row.reference_amount == 1 for row in rows)
    assert all(row.reference_unit == "kg" for row in rows)


def test_plastics_europe_normalizer_preserves_lca_and_continental_fit(
    tmp_path: Path,
) -> None:
    path = tmp_path / "plastics-europe.zip"
    spec = _bundle(path)
    rows = PlasticsEuropeParser(packages=(spec,), pdf_text_extractor=_pages).parse(path)
    raw = RawAssetReference(
        bucket="atlas",
        object_key="sources/plastics_europe/fixture.zip",
        sha256="c" * 64,
        filename="fixture.zip",
        source_url="https://plasticseurope.org/",
        size_bytes=path.stat().st_size,
        downloaded_at="2026-03-13T00:00:00Z",
    )

    factors, metrics = PlasticsEuropeNormalizer().normalize(
        rows, raw=raw, dataset_version="2026-03", parser_version="0.1.0"
    )

    assert len(factors) == 2
    assert metrics["continental_factors"] == 2
    assert all(factor.entity_type == EnvironmentalEntityType.LCA_RESULT for factor in factors)
    assert all(factor.intended_use == FactorIntendedUse.CHARACTERIZATION for factor in factors)
    assert all(not factor.default_match_eligible for factor in factors)
    assert all(factor.factor_unit == "kgCO2e/kg" for factor in factors)
    assert all(factor.applicable_geographies[0].code == "EUROPE" for factor in factors)
