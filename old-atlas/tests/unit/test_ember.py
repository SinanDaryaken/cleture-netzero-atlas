from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx

from atlas.domain.enums import (
    EnvironmentalEntityType,
    FactorIntendedUse,
    GeographicFitType,
    GeographyLevel,
)
from atlas.domain.models import RawAssetReference
from atlas.infrastructure.http import HttpAssetFetcher
from atlas.validation import QualityEngine
from sources.ember.normalizer import EmberNormalizer
from sources.ember.parser import EmberParser


def _payload() -> dict[str, object]:
    return {
        "stats": {"timestamp": "2026-08-28T00:00:00Z"},
        "data": [
            {
                "entity": "Türkiye",
                "entity_code": "TUR",
                "is_aggregate_entity": False,
                "date": "2020",
                "emissions_intensity_gco2_per_kwh": 415.5,
            },
            {
                "entity": "World",
                "entity_code": None,
                "is_aggregate_entity": True,
                "date": "2020",
                "emissions_intensity_gco2_per_kwh": 475,
            },
            {
                "entity": "Test Region",
                "entity_code": None,
                "is_aggregate_entity": True,
                "date": "2020",
                "emissions_intensity_gco2_per_kwh": -10,
            },
            {
                "entity": "Missing",
                "entity_code": "XXX",
                "is_aggregate_entity": False,
                "date": "2020",
                "emissions_intensity_gco2_per_kwh": 50,
            },
            {
                "entity": "No value",
                "entity_code": "FRA",
                "is_aggregate_entity": False,
                "date": "2020",
                "emissions_intensity_gco2_per_kwh": None,
            },
        ],
    }


async def test_ember_fetcher_hashes_data_and_redacts_api_key() -> None:
    seen_url = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_url
        seen_url = str(request.url)
        return httpx.Response(200, json=_payload())

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    snapshot = await HttpAssetFetcher(client).fetch_ember_time_series(
        "https://api.ember-energy.org/v1/carbon-intensity/yearly",
        api_key="super-secret",
        start_date="2020",
        end_date="2026",
    )
    await client.aclose()

    assert "api_key=super-secret" in seen_url
    assert "super-secret" not in str(snapshot.asset.source_url)
    assert snapshot.row_count == 5
    assert snapshot.minimum_year == 2020
    assert snapshot.maximum_year == 2020
    assert len(snapshot.revision) == 64


def test_ember_parser_and_normalizer_preserve_time_and_entity_semantics() -> None:
    content = json.dumps(_payload()).encode()
    parser = EmberParser()
    rows = parser.parse(content)
    raw = RawAssetReference(
        bucket="atlas-raw",
        object_key="sources/ember/2026/fixture.json",
        sha256="a" * 64,
        filename="fixture.json",
        source_url=("https://api.ember-energy.org/v1/carbon-intensity/yearly?start_date=2020"),
        mime_type="application/json",
        size_bytes=len(content),
        downloaded_at=datetime.now(UTC),
    )

    factors, metrics = EmberNormalizer().normalize(
        rows,
        raw=raw,
        dataset_revision="b" * 64,
        parser_version="0.1.0",
    )

    assert len(rows) == 5
    assert len(factors) == 3
    assert metrics["excluded_null_values"] == 1
    assert metrics["excluded_unmapped_geography"] == 1
    turkey = next(factor for factor in factors if factor.origin_geography.code == "TR")
    assert turkey.reference_year == 2020
    assert turkey.factor_value == Decimal("0.4155")
    assert turkey.factor_unit == "kgCO2e/kWh"
    assert turkey.geography_level == GeographyLevel.COUNTRY
    assert turkey.geographic_fit_type == GeographicFitType.COUNTRY_MODELLED
    assert turkey.entity_type == EnvironmentalEntityType.EMISSION_FACTOR
    assert turkey.default_match_eligible is True

    negative = next(factor for factor in factors if factor.factor_value < 0)
    assert negative.entity_type == EnvironmentalEntityType.REFERENCE_VALUE
    assert negative.intended_use == FactorIntendedUse.CALCULATION_INPUT
    assert negative.default_match_eligible is False
    assert not QualityEngine().validate((negative,)).findings
