from pathlib import Path

import pytest

from atlas.domain.enums import RunMode
from atlas.infrastructure.database.models import SourceRow
from atlas.infrastructure.database.repositories import AtlasRepository
from atlas.ingestion.registry import SourceRegistry


def source_row(code: str) -> SourceRow:
    source = SourceRegistry.discover(Path("sources")).get(code)
    return SourceRow(code=source.code, manifest=source.model_dump(mode="json"))


def test_annual_source_accepts_only_declared_backfill_years() -> None:
    source = source_row("DEFRA")

    assert AtlasRepository._validate_run_target(source, 2020) == RunMode.HISTORICAL_BACKFILL
    assert AtlasRepository._validate_run_target(source, 2026) == RunMode.HISTORICAL_BACKFILL

    with pytest.raises(ValueError, match="outside DEFRA coverage 2020-2026"):
        AtlasRepository._validate_run_target(source, 2019)


def test_versioned_database_rejects_synthetic_annual_backfill() -> None:
    source = source_row("IPCC")

    assert AtlasRepository._validate_run_target(source, None) == RunMode.LATEST
    with pytest.raises(ValueError, match="versioned database"):
        AtlasRepository._validate_run_target(source, 2024)


def test_unimplemented_historical_schema_is_rejected_before_queueing() -> None:
    source = source_row("AIB")

    with pytest.raises(ValueError, match="published_report_pdf is not implemented"):
        AtlasRepository._validate_run_target(source, 2021)
