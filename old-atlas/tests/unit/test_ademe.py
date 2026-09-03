from __future__ import annotations

import csv
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
import yaml

from atlas.domain.enums import FactorIntendedUse, GeographicFitType
from atlas.domain.models import RawAssetReference
from atlas.infrastructure.http import HttpAssetFetcher
from atlas.ingestion.errors import PermanentIngestionError
from atlas.validation import QualityEngine
from sources.ademe.normalizer import AdemeNormalizer
from sources.ademe.parser import EXPECTED_HEADERS, AdemeParser


def _fixture_csv(path: Path) -> None:
    with Path("sources/ademe/fixtures/base_carbone_v23_6.yaml").open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPECTED_HEADERS, delimiter=";")
        writer.writeheader()
        writer.writerows(payload)


def _raw(path: Path) -> RawAssetReference:
    return RawAssetReference(
        bucket="atlas-raw",
        object_key="sources/ademe/23.6/test.csv",
        sha256="e" * 64,
        filename=path.name,
        source_url=(
            "https://data.ademe.fr/data-fair/api/v1/datasets/"
            "base-carboner/data-files/Base_Carbone_V23.6.csv"
        ),
        size_bytes=path.stat().st_size,
        downloaded_at=datetime.now(UTC),
    )


def test_ademe_parser_and_normalizer_preserve_semantics(tmp_path: Path) -> None:
    path = tmp_path / "Base_Carbone_V23.6.csv"
    _fixture_csv(path)
    parser = AdemeParser()
    rows = parser.parse(path)
    factors, metrics = AdemeNormalizer(Path("sources/ademe/mappings.yaml")).normalize(
        rows,
        raw=_raw(path),
        dataset_version="23.6",
        parser_version="0.1.0",
    )

    assert len(rows) == 6
    assert parser.metrics["valid_factor_elements"] == 4
    assert len(factors) == 3
    assert metrics["excluded_unmapped_geography"] == 1
    assert metrics["avoided_emission_factors"] == 1

    france = next(factor for factor in factors if factor.source_factor_id.endswith("24253"))
    assert france.factor_value.as_tuple().exponent == -2
    assert france.gases.co2 is not None
    assert france.gases.ch4 is not None
    assert france.reference_year == 2023
    assert france.geographic_fit_type == GeographicFitType.COUNTRY_SPECIFIC
    assert france.origin_geography is not None
    assert france.origin_geography.code == "FR"
    assert france.methodology.lifecycle_stage == "Amont"
    assert france.methodology.details["decomposition"][0]["source_row"] == 3

    avoided = next(factor for factor in factors if factor.source_factor_id.endswith("34625"))
    assert avoided.factor_value == -335
    assert avoided.intended_use == FactorIntendedUse.AVOIDED_EMISSIONS
    assert avoided.default_match_eligible is False
    assert not QualityEngine().validate((avoided,)).requires_review

    spend = next(factor for factor in factors if factor.source_factor_id.endswith("50001"))
    assert spend.factor_value.as_tuple().exponent == -1
    assert spend.factor_value == Decimal("0.1")
    assert spend.activity_unit == "EUR_2023_ex_vat"
    assert spend.geographic_fit_type == GeographicFitType.CONTINENTAL


def test_ademe_parser_rejects_schema_drift(tmp_path: Path) -> None:
    path = tmp_path / "Base_Carbone_V24.csv"
    path.write_text("Type Ligne;Unexpected Column\n", encoding="utf-8")

    with pytest.raises(PermanentIngestionError, match="schema changed"):
        AdemeParser().parse(path)


async def test_ademe_release_revision_uses_source_data_identity() -> None:
    metadata = {
        "id": "base-carboner",
        "status": "finalized",
        "count": 18616,
        "updatedAt": "2026-08-27T00:00:00Z",
        "dataUpdatedAt": "2025-07-03T08:07:23.668Z",
        "license": {"title": "Licence Ouverte / Open Licence"},
        "file": {
            "name": "Base_Carbone_V23.6.csv",
            "md5": "39583facdba0881a15f708693f25c793",
            "size": 10761452,
        },
    }
    data_files = [
        {
            "key": "original",
            "name": "Base_Carbone_V23.6.csv",
            "url": (
                "https://data.ademe.fr/data-fair/api/v1/datasets/"
                "base-carboner/data-files/Base_Carbone_V23.6.csv"
            ),
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=data_files if request.url.path.endswith("/data-files") else metadata,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = HttpAssetFetcher(client)
    first = await fetcher.resolve_ademe_release(
        "https://data.ademe.fr/data-fair/api/v1/datasets/base-carboner"
    )
    metadata["updatedAt"] = "2026-08-28T00:00:00Z"
    second = await fetcher.resolve_ademe_release(
        "https://data.ademe.fr/data-fair/api/v1/datasets/base-carboner"
    )
    await client.aclose()

    assert first.version == "23.6"
    assert first.row_count == 18616
    assert first.revision == second.revision


@pytest.mark.skipif(
    not os.getenv("ATLAS_ADEME_CSV"),
    reason="set ATLAS_ADEME_CSV to run the official Base Carbone snapshot",
)
def test_official_ademe_snapshot() -> None:
    path = Path(os.environ["ATLAS_ADEME_CSV"])
    parser = AdemeParser()
    rows = parser.parse(path)
    factors, metrics = AdemeNormalizer(Path("sources/ademe/mappings.yaml")).normalize(
        rows,
        raw=_raw(path),
        dataset_version="23.6",
        parser_version="0.1.0",
    )

    assert len(rows) == 18616
    assert len(factors) == 6356
    assert metrics["excluded_unmapped_geography"] == 162
    assert metrics["avoided_emission_factors"] == 290
