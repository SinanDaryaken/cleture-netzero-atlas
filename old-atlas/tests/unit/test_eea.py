from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from atlas.domain.enums import (
    EnvironmentalEntityType,
    FactorValueKind,
    GeographyLevel,
)
from atlas.domain.models import RawAssetReference
from sources.eea.adapter import EeaApiClient
from sources.eea.normalizer import EeaNormalizer
from sources.eea.parser import EeaParser


def _source(record_id: int, **overrides: Any) -> dict[str, Any]:
    source: dict[str, Any] = {
        "ID": record_id,
        "NFR": "1.A.3.b.i",
        "Sector": "Road transport, passenger cars",
        "Table": "Table_3-18",
        "Type": "Tier 2 Emission Factor",
        "Technology": "Euro 6",
        "Fuel": "Petrol",
        "Abatement": "",
        "Region": "NA",
        "Pollutant": "CO2",
        "Value": 120.5,
        "Unit": "g/km",
        "CI_lower": 100,
        "CI_upper": 140,
        "Reference": "EMEP/EEA Guidebook 2023",
        "Link": "https://www.eea.europa.eu/guidebook/chapter.pdf",
        "code": "1.A.3.b.i Road transport, passenger cars",
    }
    source.update(overrides)
    return source


async def test_eea_api_client_paginates_and_hashes_stable_records() -> None:
    records = [_source(1), _source(2, Pollutant="CH4"), _source(3, Pollutant="N2O")]
    queries: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        envelope = json.loads(request.content)
        query = json.loads(envelope["source"])
        queries.append(query)
        offset = 0 if "search_after" not in query else int(query["search_after"][0])
        page = records[offset : offset + 2]
        return httpx.Response(
            200,
            json={
                "hits": {
                    "total": {"value": 3, "relation": "eq"},
                    "hits": [
                        {
                            "_index": "efdb_2026-07-08_07_12_56",
                            "_source": item,
                            "sort": [item["ID"]],
                        }
                        for item in page
                    ],
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    api = EeaApiClient(client)
    api.PAGE_SIZE = 2
    snapshot = await api.fetch_snapshot("https://efdb.apps.eea.europa.eu/tools/api", edition=2023)
    await client.aclose()

    assert snapshot.row_count == 3
    assert snapshot.index_name == "efdb_2026-07-08_07_12_56"
    assert snapshot.refreshed_at == "2026-07-08T07:12:56Z"
    assert len(snapshot.revision) == 64
    assert len(queries) == 2
    assert queries[1]["search_after"] == [2]
    assert json.loads(snapshot.asset.content or b"{}")["records"] == records


def test_eea_parser_and_normalizer_keep_non_ghg_rows_out_of_canonical_factors() -> None:
    records = [
        _source(1),
        _source(2, Pollutant="CH4", Value="1.2E-3", Unit="g/tonnes fuel"),
        _source(3, Pollutant="N2O", Value=""),
        _source(4, Pollutant="NOx", Value=0.8),
        _source(
            5,
            Pollutant="PM2.5",
            Value=95,
            Unit="%",
            Type="Tier 2 Abatement Efficiency",
        ),
        _source(
            6,
            Pollutant="Fuel consumption",
            Value=4.2,
            Unit="kg/km",
            Type="Tier 2 Fuel Consumption",
        ),
    ]
    content = json.dumps(
        {
            "edition": 2023,
            "index_name": "efdb_2026-07-08_07_12_56",
            "refreshed_at": "2026-07-08T07:12:56Z",
            "records": records,
        }
    ).encode()
    parser = EeaParser()
    document = parser.parse(content)
    raw = RawAssetReference(
        bucket="atlas-raw",
        object_key="sources/eea/2026/snapshot.json",
        sha256="a" * 64,
        filename="snapshot.json",
        source_url="https://efdb.apps.eea.europa.eu/tools/api",
        mime_type="application/json",
        size_bytes=len(content),
        downloaded_at=datetime.now(UTC),
    )

    factors, observations, metrics = EeaNormalizer().normalize(
        document.rows,
        raw=raw,
        dataset_revision="b" * 64,
        dataset_version="guidebook-2023-viewer-2026-07-08",
        index_name=document.index_name,
        refreshed_at=document.refreshed_at,
        parser_version="0.1.0",
    )

    assert len(document.rows) == 6
    assert parser.metrics["non_numeric_rows"] == 1
    assert len(factors) == 2
    assert len(observations) == 3
    assert metrics["excluded_non_numeric_rows"] == 1
    assert metrics["excluded_rows"] == 1
    assert factors[0].factor_value == Decimal("120.5")
    assert factors[0].factor_value_kind == FactorValueKind.CO2_ONLY
    assert factors[0].gases.co2 == Decimal("120.5")
    assert factors[1].factor_value_kind == FactorValueKind.GAS_EMISSION_FACTOR
    assert factors[1].gases.ch4 == Decimal("0.0012")
    assert all(factor.geography_level == GeographyLevel.CONTINENT for factor in factors)
    assert all(not factor.default_match_eligible for factor in factors)
    assert observations[0].entity_type == EnvironmentalEntityType.EMISSION_FACTOR
    assert observations[1].entity_type == EnvironmentalEntityType.CALCULATION_PARAMETER
    assert observations[2].entity_type == EnvironmentalEntityType.CALCULATION_PARAMETER
