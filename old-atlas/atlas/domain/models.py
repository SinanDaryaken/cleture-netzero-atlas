from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from atlas.domain.enums import (
    PIPELINE_STEPS,
    EnvironmentalEntityType,
    FactorIntendedUse,
    FactorValueKind,
    GeographicFitType,
    GeographyDerivation,
    GeographyLevel,
    GeographyRole,
    PipelineStep,
    ProvenanceRole,
    QualitySeverity,
    RunMode,
    RunOutcome,
    SourceHealth,
    SourceHistoryStrategy,
    SourceStatus,
    StepStatus,
)


class AtlasModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LicensePolicy(AtlasModel):
    name: str = Field(min_length=1)
    url: HttpUrl | None = None
    commercial_use: bool | None = None
    redistribution: bool | None = None
    modification: bool | None = None
    attribution_required: bool | None = None
    api_distribution: bool | None = None
    raw_data_distribution: bool | None = None
    restrictions: str | None = None
    reviewed_at: date | None = None


class IngestionPolicy(AtlasModel):
    source_type: str = Field(min_length=1)
    schedule: str = Field(description="Cron expression interpreted in UTC")
    timeout_seconds: int = Field(default=300, gt=0)
    max_attempts: int = Field(default=4, ge=1, le=10)


class SourceLocation(AtlasModel):
    landing_page: HttpUrl
    download_url: HttpUrl | None = None
    api_url: HttpUrl | None = None


class ChangeDetectionPolicy(AtlasModel):
    strategies: tuple[str, ...] = ("etag", "last_modified", "sha256")

    @model_validator(mode="after")
    def require_strategy(self) -> ChangeDetectionPolicy:
        if not self.strategies:
            raise ValueError("at least one change detection strategy is required")
        return self


class AdapterReference(AtlasModel):
    class_path: str = Field(min_length=3)
    parser_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    mapping_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")


class SourceQualityPolicy(AtlasModel):
    minimum_expected_rows: int | None = Field(default=None, ge=0)
    minimum_expected_factors: int | None = Field(default=None, ge=0)
    expected_table_factor_counts: dict[str, int] = Field(default_factory=dict)
    maximum_row_count_change_ratio: Decimal = Field(default=Decimal("0.30"), ge=0)


class SourceSchemaPolicy(AtlasModel):
    name: str = Field(min_length=1)
    parser_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    file_format: str = Field(min_length=1)
    start_year: int | None = Field(default=None, ge=1900, le=2200)
    end_year: int | None = Field(default=None, ge=1900, le=2200)
    implemented: bool = True

    @model_validator(mode="after")
    def validate_range(self) -> SourceSchemaPolicy:
        if (self.start_year is None) != (self.end_year is None):
            raise ValueError("source schema requires both start_year and end_year")
        if (
            self.start_year is not None
            and self.end_year is not None
            and self.start_year > self.end_year
        ):
            raise ValueError("source schema start_year must not exceed end_year")
        return self

    def covers(self, reference_year: int) -> bool:
        return (
            self.start_year is not None
            and self.end_year is not None
            and self.start_year <= reference_year <= self.end_year
        )


class SourceHistoryPolicy(AtlasModel):
    strategy: SourceHistoryStrategy
    start_year: int | None = Field(default=None, ge=1900, le=2200)
    end_year: int | None = Field(default=None, ge=1900, le=2200)
    publication_lag_years: int = Field(default=0, ge=0, le=10)
    preferred_asset: str = Field(min_length=1)
    master_page: HttpUrl
    release_pages: dict[int, HttpUrl] = Field(default_factory=dict)
    snapshot_endpoints: dict[str, HttpUrl] = Field(default_factory=dict)
    snapshot_parameters: dict[str, str] = Field(default_factory=dict)
    schemas: tuple[SourceSchemaPolicy, ...]
    release_expectations: dict[int, SourceQualityPolicy] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_strategy_contract(self) -> SourceHistoryPolicy:
        is_targeted_annual = self.strategy in {
            SourceHistoryStrategy.YEARLY_RELEASE,
            SourceHistoryStrategy.LAGGED_YEARLY_RELEASE,
            SourceHistoryStrategy.YEARLY_SUBMISSION,
        }
        if is_targeted_annual:
            if self.start_year is None or self.end_year is None:
                raise ValueError("annual source history requires start_year and end_year")
            if self.start_year > self.end_year:
                raise ValueError("source history start_year must not exceed end_year")
            invalid_years = set(self.release_pages) - set(range(self.start_year, self.end_year + 1))
            if invalid_years:
                raise ValueError(
                    f"release page years fall outside declared range: {sorted(invalid_years)}"
                )
            if self.snapshot_endpoints:
                raise ValueError("targeted annual source history cannot declare snapshot_endpoints")
            expected_years = set(range(self.start_year, self.end_year + 1))
            schema_years = [
                year for schema in self.schemas for year in expected_years if schema.covers(year)
            ]
            if set(schema_years) != expected_years or len(schema_years) != len(expected_years):
                raise ValueError(
                    "targeted annual source schemas must cover every year exactly once"
                )
            unexpected_expectations = set(self.release_expectations) - expected_years
            if unexpected_expectations:
                raise ValueError(
                    "release expectation years fall outside declared range: "
                    f"{sorted(unexpected_expectations)}"
                )
        else:
            if self.start_year is not None or self.end_year is not None or self.release_pages:
                raise ValueError("snapshot source history cannot declare annual releases")
            if self.publication_lag_years:
                raise ValueError("snapshot source history cannot declare a publication lag")
            if not self.snapshot_endpoints:
                raise ValueError("snapshot source history requires snapshot_endpoints")
            if len(self.schemas) != 1 or any(
                schema.start_year is not None or schema.end_year is not None
                for schema in self.schemas
            ):
                raise ValueError("snapshot source history requires one unbounded schema")
            if self.release_expectations:
                raise ValueError("snapshot source history cannot declare annual expectations")

        if (
            self.strategy == SourceHistoryStrategy.LAGGED_YEARLY_RELEASE
            and self.publication_lag_years == 0
        ):
            raise ValueError("lagged annual source history requires publication_lag_years")
        if (
            self.strategy == SourceHistoryStrategy.YEARLY_RELEASE
            and self.publication_lag_years != 0
        ):
            raise ValueError("yearly source history cannot declare a publication lag")
        return self

    @property
    def reference_years(self) -> tuple[int, ...]:
        if self.start_year is None or self.end_year is None:
            return ()
        return tuple(range(self.start_year, self.end_year + 1))

    @property
    def supports_targeted_backfill(self) -> bool:
        return self.strategy in {
            SourceHistoryStrategy.YEARLY_RELEASE,
            SourceHistoryStrategy.LAGGED_YEARLY_RELEASE,
            SourceHistoryStrategy.YEARLY_SUBMISSION,
        }

    def schema_for(self, reference_year: int | None = None) -> SourceSchemaPolicy:
        if reference_year is None:
            if not self.supports_targeted_backfill:
                return self.schemas[0]
            if self.end_year is None:
                raise ValueError("annual source history end_year is unavailable")
            reference_year = self.end_year
        for schema in self.schemas:
            if schema.covers(reference_year):
                return schema
        raise ValueError(f"no source schema is registered for reference year {reference_year}")


class Geography(AtlasModel):
    level: GeographyLevel
    code: str
    name: str | None = None


class GeographyAssignment(AtlasModel):
    """A source-backed semantic role for a geography.

    Missing roles are intentionally omitted. They are never inferred as GLOBAL.
    """

    role: GeographyRole
    geography: Geography
    derivation: GeographyDerivation
    source_field: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class SourceDefinition(AtlasModel):
    code: str = Field(pattern=r"^[A-Z0-9_]+$")
    name: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    region: str | None = None
    status: SourceStatus = SourceStatus.PLANNED
    health: SourceHealth = SourceHealth.DISABLED
    license: LicensePolicy
    ingestion: IngestionPolicy
    location: SourceLocation
    change_detection: ChangeDetectionPolicy = ChangeDetectionPolicy()
    adapter: AdapterReference
    history: SourceHistoryPolicy
    data_types: tuple[EnvironmentalEntityType, ...] = (EnvironmentalEntityType.EMISSION_FACTOR,)
    use_contexts: tuple[str, ...] = ()
    standards: tuple[str, ...] = ()
    quality: SourceQualityPolicy = SourceQualityPolicy()
    coverage: tuple[Geography, ...] = ()


class ChangeCheckResult(AtlasModel):
    changed: bool
    revision: str | None = None
    etag: str | None = None
    last_modified: datetime | None = None
    reason: str

    @model_validator(mode="after")
    def changed_requires_revision(self) -> ChangeCheckResult:
        if self.changed and not self.revision:
            raise ValueError("changed source checks must provide a revision")
        return self


class FetchedAsset(AtlasModel):
    filename: str = Field(min_length=1)
    content: bytes | None = None
    local_path: Path | None = None
    source_url: HttpUrl
    mime_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    downloaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def require_content_source(self) -> FetchedAsset:
        if self.content is None and self.local_path is None:
            raise ValueError("fetched asset requires content or local_path")
        return self


class RawAssetReference(AtlasModel):
    bucket: str
    object_key: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    filename: str
    source_url: HttpUrl
    mime_type: str | None = None
    size_bytes: int = Field(ge=0)
    downloaded_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProcessingArtifactReference(AtlasModel):
    layer: str
    bucket: str
    object_key: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    row_count: int = Field(ge=0)


class ParsedRecord(AtlasModel):
    data: dict[str, Any]
    source_row: int | None = Field(default=None, ge=0)
    source_sheet: str | None = None
    source_table: str | None = None


class SourceObservation(AtlasModel):
    """A source-native measurement retained for audit and deterministic reprocessing.

    Observations are deliberately not Atlas factors. They may represent activity
    data, reported emissions, calculation parameters, or gas-specific implied
    factors that still need curation before they are safe for matching.
    """

    observation_id: str = Field(min_length=1)
    entity_type: EnvironmentalEntityType
    name: str = Field(min_length=1)
    value: Decimal
    unit: str = Field(min_length=1)
    reference_year: int | None = Field(default=None, ge=1900, le=2200)
    gas: str | None = None
    source_category: str | None = None
    source_subcategory: str | None = None
    provenance: FactorProvenance
    attributes: dict[str, Any] = Field(default_factory=dict)


class FactorProvenance(AtlasModel):
    role: ProvenanceRole = ProvenanceRole.TOTAL
    raw_asset_key: str
    original_url: HttpUrl
    downloaded_at: datetime
    file_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    original_file: str
    parser_version: str
    mapping_version: str
    sheet: str | None = None
    table: str | None = None
    row: int | None = Field(default=None, ge=0)
    column_number: int | None = Field(default=None, ge=1)
    column_name: str | None = None
    original_factor_name: str | None = None
    original_unit: str | None = None


class GasValues(AtlasModel):
    co2: Decimal | None = None
    ch4: Decimal | None = None
    n2o: Decimal | None = None
    co2e: Decimal | None = None


class Methodology(AtlasModel):
    scope: str | None = None
    lifecycle_stage: str | None = None
    system_boundary: str | None = None
    gwp_standard: str | None = None
    methodology: str | None = None
    uncertainty: Decimal | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class CanonicalFactor(AtlasModel):
    factor_id: str = Field(min_length=1)
    logical_factor_id: str = Field(min_length=1)
    source_code: str = Field(pattern=r"^[A-Z0-9_]+$")
    dataset_id: str
    dataset_version_id: str
    source_factor_id: str | None = None
    name: str = Field(min_length=1)
    description: str | None = None
    taxonomy_code: str | None = None
    source_category: str | None = None
    source_subcategory: str | None = None
    activity_type: str = Field(min_length=1)
    activity_unit: str = Field(min_length=1)
    factor_value: Decimal
    factor_unit: str = Field(min_length=1)
    entity_type: EnvironmentalEntityType = EnvironmentalEntityType.EMISSION_FACTOR
    factor_value_kind: FactorValueKind = FactorValueKind.CO2E_TOTAL
    intended_use: FactorIntendedUse = FactorIntendedUse.INVENTORY
    gases: GasValues = GasValues()
    origin_geography: Geography | None = None
    applicable_geographies: tuple[Geography, ...] = ()
    geography_roles: tuple[GeographyAssignment, ...] = ()
    geography_level: GeographyLevel
    geographic_specificity: int = Field(ge=0, le=6)
    geographic_fit_type: GeographicFitType
    valid_from: date | None = None
    valid_to: date | None = None
    reference_year: int | None = Field(default=None, ge=1900, le=2200)
    methodology: Methodology = Methodology()
    data_quality: str | None = None
    provenance: FactorProvenance
    component_provenance: tuple[FactorProvenance, ...] = ()
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def default_match_eligible(self) -> bool:
        return (
            self.entity_type
            in {
                EnvironmentalEntityType.EMISSION_FACTOR,
                EnvironmentalEntityType.IMPLIED_EMISSION_FACTOR,
            }
            and self.factor_value_kind == FactorValueKind.CO2E_TOTAL
            and self.intended_use == FactorIntendedUse.INVENTORY
        )


class QualityFinding(AtlasModel):
    rule_code: str
    severity: QualitySeverity
    message: str
    factor_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class QualityReport(AtlasModel):
    checked_records: int = Field(ge=0)
    findings: tuple[QualityFinding, ...] = ()

    @property
    def requires_review(self) -> bool:
        return any(
            finding.severity in {QualitySeverity.FAIL, QualitySeverity.REVIEW_REQUIRED}
            for finding in self.findings
        )

    @property
    def has_warnings(self) -> bool:
        return any(finding.severity == QualitySeverity.WARNING for finding in self.findings)


class ComparisonReport(AtlasModel):
    added: int = Field(default=0, ge=0)
    removed: int = Field(default=0, ge=0)
    changed: int = Field(default=0, ge=0)
    unchanged: int = Field(default=0, ge=0)
    review_reasons: tuple[str, ...] = ()

    @property
    def requires_review(self) -> bool:
        return bool(self.review_reasons)


class RunStepState(AtlasModel):
    step: PipelineStep
    status: StepStatus = StepStatus.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    attempt: int = Field(default=0, ge=0)
    message: str | None = None


class PipelineRun(AtlasModel):
    id: UUID = Field(default_factory=uuid4)
    source_code: str
    run_mode: RunMode = RunMode.LATEST
    requested_reference_year: int | None = Field(default=None, ge=1900, le=2200)
    requested_revision: str | None = None
    outcome: RunOutcome = RunOutcome.RUNNING
    failure_retryable: bool = False
    error_class: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    steps: dict[PipelineStep, RunStepState] = Field(
        default_factory=lambda: {step: RunStepState(step=step) for step in PIPELINE_STEPS}
    )


class PipelineContext(AtlasModel):
    source: SourceDefinition
    run: PipelineRun
    source_dataset_version: str | None = None
    source_published_at: datetime | None = None
    parser_version: str | None = None
    check_result: ChangeCheckResult | None = None
    fetched_asset: FetchedAsset | None = None
    raw_asset: RawAssetReference | None = None
    parsed_artifact: ProcessingArtifactReference | None = None
    normalized_artifact: ProcessingArtifactReference | None = None
    parsed_records: tuple[ParsedRecord, ...] = ()
    source_observations: tuple[SourceObservation, ...] = ()
    normalized_factors: tuple[CanonicalFactor, ...] = ()
    quality_report: QualityReport | None = None
    comparison_report: ComparisonReport | None = None
    dataset_version_id: str | None = None
    review_required: bool = False
    metrics: dict[str, int] = Field(default_factory=dict)

    @property
    def effective_parser_version(self) -> str:
        return self.parser_version or self.source.adapter.parser_version
