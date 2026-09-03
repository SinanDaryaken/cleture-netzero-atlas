from datetime import UTC, datetime
from decimal import Decimal

from atlas.domain.enums import (
    GeographicFitType,
    GeographyLevel,
    PipelineStep,
    RunOutcome,
    StepStatus,
)
from atlas.domain.models import (
    CanonicalFactor,
    ChangeCheckResult,
    ComparisonReport,
    FactorProvenance,
    FetchedAsset,
    Geography,
    ParsedRecord,
    PipelineContext,
    QualityFinding,
    QualityReport,
    RawAssetReference,
    SourceDefinition,
)
from atlas.ingestion.errors import RetryableIngestionError
from atlas.orchestration import PipelineEngine
from atlas.validation import QualityEngine


def source() -> SourceDefinition:
    return SourceDefinition.model_validate(
        {
            "code": "TEST",
            "name": "Test Source",
            "publisher": "Test Publisher",
            "status": "active",
            "health": "healthy",
            "license": {"name": "Test License"},
            "ingestion": {"source_type": "json", "schedule": "0 0 * * *"},
            "location": {"landing_page": "https://example.test/source"},
            "adapter": {
                "class_path": "tests.FakeAdapter",
                "parser_version": "0.1.0",
                "mapping_version": "0.1.0",
            },
            "history": {
                "strategy": "versioned_database",
                "preferred_asset": "api_snapshot",
                "master_page": "https://example.test/source",
                "snapshot_endpoints": {"records": "https://example.test/records"},
                "schemas": [
                    {
                        "name": "api_snapshot",
                        "parser_version": "0.1.0",
                        "file_format": "json",
                    }
                ],
            },
        }
    )


def canonical_factor() -> CanonicalFactor:
    return CanonicalFactor(
        factor_id="atlas:test:electricity:2026:tr",
        logical_factor_id="atlas:test:electricity:tr",
        source_code="TEST",
        dataset_id="test",
        dataset_version_id="test:2026",
        name="Electricity",
        taxonomy_code="atlas.energy.electricity",
        activity_type="electricity",
        activity_unit="kWh",
        factor_value=Decimal("0.40"),
        factor_unit="kgCO2e/kWh",
        origin_geography=Geography(level=GeographyLevel.COUNTRY, code="TR"),
        applicable_geographies=(Geography(level=GeographyLevel.COUNTRY, code="TR"),),
        geography_level=GeographyLevel.COUNTRY,
        geographic_specificity=3,
        geographic_fit_type=GeographicFitType.COUNTRY_SPECIFIC,
        reference_year=2026,
        provenance=FactorProvenance(
            raw_asset_key="sources/test/2026/a/original.json",
            original_url="https://example.test/source.json",
            downloaded_at=datetime.now(UTC),
            file_checksum="a" * 64,
            original_file="original.json",
            parser_version="0.1.0",
            mapping_version="0.1.0",
            row=1,
        ),
    )


class FakeAdapter:
    def __init__(self, *, changed: bool = True, review: bool = False) -> None:
        self.changed = changed
        self.review = review
        self.calls: list[str] = []

    async def check(self, context: PipelineContext) -> ChangeCheckResult:
        self.calls.append("check")
        return ChangeCheckResult(
            changed=self.changed,
            revision="sha256:a" if self.changed else None,
            reason="changed" if self.changed else "same checksum",
        )

    async def fetch(self, context: PipelineContext) -> FetchedAsset:
        self.calls.append("fetch")
        return FetchedAsset(
            filename="source.json",
            content=b"{}",
            source_url="https://example.test/source.json",
            mime_type="application/json",
        )

    async def store_raw(self, context: PipelineContext) -> RawAssetReference:
        self.calls.append("store_raw")
        assert context.fetched_asset is not None
        return RawAssetReference(
            bucket="atlas-raw",
            object_key="sources/test/2026/a/original.json",
            sha256="a" * 64,
            filename="source.json",
            source_url=context.fetched_asset.source_url,
            mime_type=context.fetched_asset.mime_type,
            size_bytes=len(context.fetched_asset.content),
            downloaded_at=context.fetched_asset.downloaded_at,
        )

    async def parse(self, context: PipelineContext) -> tuple[ParsedRecord, ...]:
        self.calls.append("parse")
        return (ParsedRecord(data={"name": "Electricity"}, source_row=1),)

    async def normalize(self, context: PipelineContext) -> tuple[CanonicalFactor, ...]:
        self.calls.append("normalize")
        return (canonical_factor(),)

    async def validate(self, context: PipelineContext) -> QualityReport:
        self.calls.append("validate")
        report = QualityEngine().validate(context.normalized_factors)
        if not self.review:
            return report
        return QualityReport(
            checked_records=report.checked_records,
            findings=(
                QualityFinding(
                    rule_code="test.review",
                    severity="review_required",
                    message="manual review requested",
                ),
            ),
        )

    async def compare(self, context: PipelineContext) -> ComparisonReport:
        self.calls.append("compare")
        return ComparisonReport(added=1)

    async def version(self, context: PipelineContext) -> str:
        self.calls.append("version")
        return "test:2026"

    async def publish(self, context: PipelineContext) -> None:
        self.calls.append("publish")


class FailingAdapter(FakeAdapter):
    async def fetch(self, context: PipelineContext) -> FetchedAsset:
        raise RetryableIngestionError("source timeout")


async def test_no_change_stops_after_check() -> None:
    adapter = FakeAdapter(changed=False)

    context = await PipelineEngine().execute(source(), adapter)

    assert context.run.outcome == RunOutcome.NO_CHANGE
    assert adapter.calls == ["check"]
    assert context.run.steps[PipelineStep.FETCH].status == StepStatus.SKIPPED


async def test_success_runs_all_fixed_steps() -> None:
    adapter = FakeAdapter()

    context = await PipelineEngine().execute(source(), adapter)

    assert context.run.outcome == RunOutcome.SUCCESS
    assert adapter.calls == [step.value for step in PipelineStep]
    assert all(state.status == StepStatus.SUCCESS for state in context.run.steps.values())


async def test_review_gate_prevents_version_and_publish() -> None:
    adapter = FakeAdapter(review=True)

    context = await PipelineEngine().execute(source(), adapter)

    assert context.run.outcome == RunOutcome.REVIEW_REQUIRED
    assert context.run.steps[PipelineStep.VALIDATE].status == StepStatus.REVIEW_REQUIRED
    assert context.run.steps[PipelineStep.VERSION].status == StepStatus.SUCCESS
    assert context.run.steps[PipelineStep.PUBLISH].status == StepStatus.SKIPPED
    assert "version" in adapter.calls
    assert "publish" not in adapter.calls


async def test_retryable_failure_is_classified_and_stops_pipeline() -> None:
    context = await PipelineEngine().execute(source(), FailingAdapter(), attempt=2)

    assert context.run.outcome == RunOutcome.FAILED
    assert context.run.failure_retryable is True
    assert context.run.error_class == "RetryableIngestionError"
    assert context.run.steps[PipelineStep.FETCH].status == StepStatus.FAILED
    assert context.run.steps[PipelineStep.FETCH].attempt == 2
    assert context.run.steps[PipelineStep.PARSE].status == StepStatus.SKIPPED
