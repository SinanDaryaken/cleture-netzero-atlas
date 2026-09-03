from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from atlas.infrastructure.database.models import FactorRow, FactorVersionRow, SourceRow
from atlas.infrastructure.database.repositories import (
    AtlasRepository,
    _reference_year_preference,
)


def test_temporal_factor_payload_exposes_business_and_system_time() -> None:
    logical = FactorRow(
        id=uuid4(),
        source_id=uuid4(),
        logical_id="atlas:defra:diesel:gb",
    )
    version_id = uuid4()
    superseded_id = uuid4()
    effective_from = datetime(2024, 6, 10, tzinfo=UTC)
    effective_to = datetime(2026, 2, 10, tzinfo=UTC)
    version = FactorVersionRow(
        id=version_id,
        factor_id=logical.id,
        dataset_version_id=uuid4(),
        source_factor_id="diesel",
        name="Diesel",
        taxonomy_code="atlas.energy.diesel",
        activity_type="fuel",
        activity_unit="l",
        factor_value=Decimal("2.432"),
        factor_unit="kgCO2e/l",
        entity_type="emission_factor",
        factor_value_kind="co2e_total",
        intended_use="inventory",
        gases={},
        origin_geography={"level": "country", "code": "GB"},
        applicable_geographies=[{"level": "country", "code": "GB"}],
        geography_level="country",
        geographic_specificity=3,
        geographic_fit_type="country_specific",
        reference_year=2022,
        valid_from=date(2022, 1, 1),
        valid_to=date(2023, 1, 1),
        source_published_at=datetime(2022, 6, 20, tzinfo=UTC),
        retrieved_at=effective_from,
        system_effective_from=effective_from,
        system_effective_to=effective_to,
        superseded_at=effective_to,
        supersedes_version_id=superseded_id,
        version_status="superseded",
        methodology={},
        source_payload={},
    )
    source = SourceRow(
        id=uuid4(),
        license_id=uuid4(),
        code="DEFRA",
        name="DEFRA",
        publisher="DESNZ",
        status="active",
        health="healthy",
        schedule="0 6 * * *",
        manifest={},
    )

    payload = AtlasRepository._factor_payload(logical, version, source)

    assert payload["reference_year"] == 2022
    assert payload["entity_type"] == "emission_factor"
    assert payload["valid_from"] == date(2022, 1, 1)
    assert payload["valid_to"] == date(2023, 1, 1)
    assert payload["published_at"] == datetime(2022, 6, 20, tzinfo=UTC)
    assert payload["retrieved_at"] == effective_from
    assert payload["effective_from"] == effective_from
    assert payload["effective_to"] == effective_to
    assert payload["version_status"] == "superseded"
    assert payload["supersedes_version_id"] == str(superseded_id)


def test_reference_year_selection_prefers_closest_dated_version() -> None:
    requested = 2022
    years = (None, 2025, 2023, 2021, 2022)

    selected = min(years, key=lambda year: _reference_year_preference(requested, year))

    assert selected == 2022


def test_reference_year_selection_prefers_past_on_equal_distance() -> None:
    selected = min(
        (2022, 2024),
        key=lambda year: _reference_year_preference(2023, year),
    )

    assert selected == 2022


def test_reference_year_selection_marks_undated_as_fallback() -> None:
    assert _reference_year_preference(2025, 2024) < _reference_year_preference(2025, None)
    assert _reference_year_preference(None, 2024) < _reference_year_preference(None, None)
