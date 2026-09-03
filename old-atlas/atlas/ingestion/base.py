from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from atlas.domain.enums import QualitySeverity
from atlas.domain.models import (
    CanonicalFactor,
    ChangeCheckResult,
    ComparisonReport,
    FetchedAsset,
    ParsedRecord,
    PipelineContext,
    QualityFinding,
    QualityReport,
    RawAssetReference,
)
from atlas.infrastructure.database.repositories import AtlasRepository
from atlas.ports.storage import ObjectStorage
from atlas.validation import QualityEngine


class BaseAtlasSourceAdapter:
    def __init__(
        self,
        *,
        repository: AtlasRepository,
        storage: ObjectStorage,
        quality_engine: QualityEngine | None = None,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.quality_engine = quality_engine or QualityEngine()

    async def check(self, context: PipelineContext) -> ChangeCheckResult:
        raise NotImplementedError

    async def fetch(self, context: PipelineContext) -> FetchedAsset:
        raise NotImplementedError

    async def parse(self, context: PipelineContext) -> tuple[ParsedRecord, ...]:
        raise NotImplementedError

    async def normalize(self, context: PipelineContext) -> tuple[CanonicalFactor, ...]:
        raise NotImplementedError

    async def store_raw(self, context: PipelineContext) -> RawAssetReference:
        if context.fetched_asset is None:
            raise ValueError("fetch must complete before store_raw")
        raw = await self.storage.store_raw(context.source, context.fetched_asset)
        await self.repository.record_raw_asset(context.source.code, raw)
        return raw

    async def validate(self, context: PipelineContext) -> QualityReport:
        report = self.quality_engine.validate(context.normalized_factors)
        findings = list(report.findings)
        release_year = context.metrics.get("release_year")
        quality_policy = context.source.quality
        if release_year is not None:
            quality_policy = context.source.history.release_expectations.get(
                release_year, quality_policy
            )
        minimum_rows = quality_policy.minimum_expected_rows
        if minimum_rows is not None and len(context.parsed_records) < minimum_rows:
            findings.append(
                QualityFinding(
                    rule_code="dataset.minimum_rows",
                    severity=QualitySeverity.FAIL,
                    message=(
                        f"parsed row count {len(context.parsed_records)} is below "
                        f"expected minimum {minimum_rows}"
                    ),
                )
            )
        minimum_factors = quality_policy.minimum_expected_factors
        if minimum_factors is not None and len(context.normalized_factors) < minimum_factors:
            findings.append(
                QualityFinding(
                    rule_code="dataset.minimum_factors",
                    severity=QualitySeverity.FAIL,
                    message=(
                        f"normalized factor count {len(context.normalized_factors)} is below "
                        f"expected minimum {minimum_factors}"
                    ),
                )
            )
        for table, expected in quality_policy.expected_table_factor_counts.items():
            actual = context.metrics.get(f"table_{table}_factors")
            if actual != expected:
                findings.append(
                    QualityFinding(
                        rule_code="dataset.table_factor_count",
                        severity=QualitySeverity.REVIEW_REQUIRED,
                        message=f"table {table} produced {actual!r} factors; expected {expected}",
                        details={"table": table, "expected": expected, "actual": actual},
                    )
                )
        license_policy = context.source.license
        if license_policy.commercial_use is not True or license_policy.api_distribution is not True:
            findings.append(
                QualityFinding(
                    rule_code="license.api_distribution_unapproved",
                    severity=QualitySeverity.REVIEW_REQUIRED,
                    message=(
                        "commercial use and API distribution rights require explicit approval"
                    ),
                    details={
                        "license": license_policy.name,
                        "commercial_use": license_policy.commercial_use,
                        "api_distribution": license_policy.api_distribution,
                    },
                )
            )
        return QualityReport(
            checked_records=len(context.normalized_factors), findings=tuple(findings)
        )

    async def compare(self, context: PipelineContext) -> ComparisonReport:
        years = {
            factor.reference_year
            for factor in context.normalized_factors
            if factor.reference_year is not None
        }
        reference_year = next(iter(years)) if len(years) == 1 else None
        previous = await self.repository.published_factor_values(
            context.source.code,
            reference_year=reference_year,
        )
        current = {
            factor.source_factor_id or factor.logical_factor_id: factor.factor_value
            for factor in context.normalized_factors
        }
        if not previous:
            return ComparisonReport(
                added=len(current),
                review_reasons=("initial_dataset",),
            )
        previous_keys = set(previous)
        current_keys = set(current)
        added = current_keys - previous_keys
        removed = previous_keys - current_keys
        changed = 0
        unchanged = 0
        large_changes = 0
        threshold = context.source.quality.maximum_row_count_change_ratio
        for key in previous_keys & current_keys:
            old = Decimal(previous[key])
            new = current[key]
            if old == new:
                unchanged += 1
                continue
            changed += 1
            if old == 0 or abs((new - old) / old) > threshold:
                large_changes += 1
        reasons: list[str] = []
        if large_changes:
            reasons.append(f"large_value_changes:{large_changes}")
        baseline_size = max(len(previous), 1)
        row_change_ratio = Decimal(abs(len(current) - len(previous))) / Decimal(baseline_size)
        if row_change_ratio > threshold:
            reasons.append("unexpected_row_count_change")
        return ComparisonReport(
            added=len(added),
            removed=len(removed),
            changed=changed,
            unchanged=unchanged,
            review_reasons=tuple(reasons),
        )

    async def version(self, context: PipelineContext) -> str:
        return await self.repository.persist_candidate(context)

    async def publish(self, context: PipelineContext) -> None:
        if context.dataset_version_id is None:
            raise ValueError("version must complete before publish")
        await self.repository.publish_version(UUID(context.dataset_version_id))

    async def close(self) -> None:
        """Release adapter-owned resources. Source adapters may override this hook."""
