from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(UTC)


JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


class CountryRow(Base):
    __tablename__ = "atlas_countries"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    alpha3: Mapped[str] = mapped_column(String(3), unique=True, index=True)
    numeric_code: Mapped[str | None] = mapped_column(String(3), unique=True)
    canonical_name: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    registry_version: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CountryLabelRow(Base):
    __tablename__ = "atlas_country_labels"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    country_code: Mapped[str] = mapped_column(
        ForeignKey("atlas_countries.code", ondelete="CASCADE"), index=True
    )
    language: Mapped[str] = mapped_column(String(8), index=True)
    label: Mapped[str] = mapped_column(String(255))
    normalized_label: Mapped[str] = mapped_column(String(255), index=True)
    label_type: Mapped[str] = mapped_column(String(32), index=True)
    source: Mapped[str] = mapped_column(String(64))
    review_status: Mapped[str] = mapped_column(String(32), default="approved", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "country_code",
            "language",
            "normalized_label",
            name="uq_atlas_country_label",
        ),
    )


class LicenseRow(Base):
    __tablename__ = "atlas_licenses"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    url: Mapped[str | None] = mapped_column(Text)
    commercial_use: Mapped[bool | None] = mapped_column(Boolean)
    redistribution: Mapped[bool | None] = mapped_column(Boolean)
    modification: Mapped[bool | None] = mapped_column(Boolean)
    attribution_required: Mapped[bool | None] = mapped_column(Boolean)
    api_distribution: Mapped[bool | None] = mapped_column(Boolean)
    raw_data_distribution: Mapped[bool | None] = mapped_column(Boolean)
    restrictions: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SourceRow(Base):
    __tablename__ = "atlas_sources"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    license_id: Mapped[UUID] = mapped_column(ForeignKey("atlas_licenses.id"))
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    publisher: Mapped[str] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(ForeignKey("atlas_countries.code"))
    region: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), index=True)
    health: Mapped[str] = mapped_column(String(32))
    schedule: Mapped[str] = mapped_column(String(64))
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_successful_import_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class SourceCheckRow(Base):
    __tablename__ = "atlas_source_checks"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("atlas_sources.id"), index=True)
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey("atlas_source_runs.id"), index=True)
    changed: Mapped[bool] = mapped_column(Boolean)
    revision: Mapped[str | None] = mapped_column(String(512))
    etag: Mapped[str | None] = mapped_column(String(512))
    last_modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SourceRunRow(Base):
    __tablename__ = "atlas_source_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("atlas_sources.id"), index=True)
    outcome: Mapped[str] = mapped_column(String(32), index=True, default="running")
    requested_by: Mapped[str] = mapped_column(String(64), default="manual")
    run_mode: Mapped[str] = mapped_column(String(32), default="latest")
    requested_reference_year: Mapped[int | None] = mapped_column(Integer)
    requested_revision: Mapped[str | None] = mapped_column(String(512))
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    failure_retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    error_class: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_atlas_source_active_run",
            "source_id",
            unique=True,
            postgresql_where=text("outcome = 'running'"),
        ),
    )


class RunStepRow(Base):
    __tablename__ = "atlas_run_steps"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("atlas_source_runs.id", ondelete="CASCADE"), index=True
    )
    step: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("run_id", "step", name="uq_atlas_run_step"),)


class DatasetRow(Base):
    __tablename__ = "atlas_datasets"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("atlas_sources.id"), unique=True)
    code: Mapped[str] = mapped_column(String(128), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    current_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("atlas_dataset_versions.id", use_alter=True, name="fk_dataset_current_version")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DatasetVersionRow(Base):
    __tablename__ = "atlas_dataset_versions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("atlas_datasets.id"), index=True)
    source_run_id: Mapped[UUID] = mapped_column(ForeignKey("atlas_source_runs.id"), unique=True)
    raw_asset_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("atlas_raw_assets.id", name="fk_dataset_version_raw_asset")
    )
    version_key: Mapped[str] = mapped_column(String(255))
    release_year: Mapped[int | None] = mapped_column(Integer)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source_revision: Mapped[str | None] = mapped_column(String(512))
    checksum: Mapped[str] = mapped_column(String(64))
    parser_version: Mapped[str] = mapped_column(String(64))
    mapping_version: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), index=True)
    parsed_row_count: Mapped[int] = mapped_column(Integer, default=0)
    normalized_factor_count: Mapped[int] = mapped_column(Integer, default=0)
    excluded_row_count: Mapped[int] = mapped_column(Integer, default=0)
    comparison: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    system_effective_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    system_effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("atlas_dataset_versions.id", name="fk_dataset_version_supersedes"),
        index=True,
    )
    version_status: Mapped[str] = mapped_column(String(32), index=True, default="candidate")

    __table_args__ = (
        UniqueConstraint(
            "dataset_id",
            "checksum",
            "parser_version",
            "mapping_version",
            name="uq_atlas_dataset_processing_version",
        ),
    )


class RawAssetRow(Base):
    __tablename__ = "atlas_raw_assets"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("atlas_sources.id"), index=True)
    bucket: Mapped[str] = mapped_column(String(128))
    object_key: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    filename: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)

    __table_args__ = (
        UniqueConstraint("source_id", "sha256", name="uq_atlas_raw_source_checksum"),
        UniqueConstraint("bucket", "object_key", name="uq_atlas_raw_object"),
    )


class ProcessingArtifactRow(Base):
    __tablename__ = "atlas_processing_artifacts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    dataset_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("atlas_dataset_versions.id"), index=True
    )
    layer: Mapped[str] = mapped_column(String(32))
    bucket: Mapped[str] = mapped_column(String(128))
    object_key: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    row_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        UniqueConstraint("dataset_version_id", "layer", name="uq_atlas_processing_layer"),
    )


class SourceObservationRow(Base):
    __tablename__ = "atlas_source_observations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    dataset_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("atlas_dataset_versions.id", ondelete="CASCADE"), index=True
    )
    raw_asset_id: Mapped[UUID] = mapped_column(ForeignKey("atlas_raw_assets.id"), index=True)
    observation_id: Mapped[str] = mapped_column(String(512))
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(Text)
    value: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    unit: Mapped[str] = mapped_column(String(255))
    reference_year: Mapped[int | None] = mapped_column(Integer, index=True)
    gas: Mapped[str | None] = mapped_column(String(32), index=True)
    source_category: Mapped[str | None] = mapped_column(Text)
    source_subcategory: Mapped[str | None] = mapped_column(Text)
    source_coordinates: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id",
            "observation_id",
            name="uq_atlas_source_observation_version",
        ),
        Index(
            "ix_atlas_source_observations_version_entity_year",
            "dataset_version_id",
            "entity_type",
            "reference_year",
        ),
    )


class FactorRow(Base):
    __tablename__ = "atlas_factors"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("atlas_sources.id"), index=True)
    logical_id: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FactorVersionRow(Base):
    __tablename__ = "atlas_factor_versions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    factor_id: Mapped[UUID] = mapped_column(ForeignKey("atlas_factors.id"), index=True)
    dataset_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("atlas_dataset_versions.id"), index=True
    )
    source_factor_id: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    taxonomy_code: Mapped[str] = mapped_column(String(255), index=True)
    activity_type: Mapped[str] = mapped_column(String(128))
    activity_unit: Mapped[str] = mapped_column(String(128))
    factor_value: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    factor_unit: Mapped[str] = mapped_column(String(255))
    entity_type: Mapped[str] = mapped_column(String(40), index=True, default="emission_factor")
    factor_value_kind: Mapped[str] = mapped_column(String(32), index=True)
    intended_use: Mapped[str] = mapped_column(String(32), index=True)
    gases: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    origin_geography: Mapped[dict[str, Any] | None] = mapped_column(JSON_TYPE)
    applicable_geographies: Mapped[list[dict[str, Any]]] = mapped_column(JSON_TYPE, default=list)
    geography_roles: Mapped[list[dict[str, Any]]] = mapped_column(JSON_TYPE, default=list)
    geography_level: Mapped[str] = mapped_column(String(32), index=True)
    geographic_specificity: Mapped[int] = mapped_column(Integer, index=True)
    geographic_fit_type: Mapped[str] = mapped_column(String(32), index=True)
    reference_year: Mapped[int | None] = mapped_column(Integer, index=True)
    valid_from: Mapped[date | None] = mapped_column(Date, index=True)
    valid_to: Mapped[date | None] = mapped_column(Date, index=True)
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    system_effective_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    system_effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("atlas_factor_versions.id", name="fk_factor_version_supersedes"),
        index=True,
    )
    version_status: Mapped[str] = mapped_column(String(32), index=True, default="candidate")
    methodology: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    data_quality: Mapped[str | None] = mapped_column(String(64))
    source_payload: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id", "source_factor_id", name="uq_atlas_factor_source_version"
        ),
        Index(
            "ix_atlas_factor_versions_applicable_geographies",
            "applicable_geographies",
            postgresql_using="gin",
            postgresql_ops={"applicable_geographies": "jsonb_path_ops"},
        ),
    )


class ProvenanceRow(Base):
    __tablename__ = "atlas_provenance"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    factor_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("atlas_factor_versions.id", ondelete="CASCADE"), index=True
    )
    raw_asset_id: Mapped[UUID] = mapped_column(ForeignKey("atlas_raw_assets.id"), index=True)
    role: Mapped[str] = mapped_column(String(32))
    sheet: Mapped[str | None] = mapped_column(Text)
    table_name: Mapped[str | None] = mapped_column(Text)
    row_number: Mapped[int | None] = mapped_column(Integer)
    column_number: Mapped[int | None] = mapped_column(Integer)
    column_name: Mapped[str | None] = mapped_column(Text)
    original_factor_name: Mapped[str | None] = mapped_column(Text)
    original_unit: Mapped[str | None] = mapped_column(Text)
    parser_version: Mapped[str] = mapped_column(String(64))
    mapping_version: Mapped[str] = mapped_column(String(64))

    __table_args__ = (
        UniqueConstraint("factor_version_id", "role", name="uq_atlas_factor_provenance_role"),
    )


class TaxonomyRow(Base):
    __tablename__ = "atlas_taxonomy"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    parent_code: Mapped[str | None] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SectorRow(Base):
    __tablename__ = "atlas_sectors"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    registry_version: Mapped[str] = mapped_column(String(64), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SectorLabelRow(Base):
    __tablename__ = "atlas_sector_labels"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    sector_code: Mapped[str] = mapped_column(
        ForeignKey("atlas_sectors.code", ondelete="CASCADE"), index=True
    )
    language: Mapped[str] = mapped_column(String(8), index=True)
    label: Mapped[str] = mapped_column(String(255))
    normalized_label: Mapped[str] = mapped_column(String(255), index=True)
    source: Mapped[str] = mapped_column(String(64))
    review_status: Mapped[str] = mapped_column(String(32), default="approved", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "sector_code",
            "language",
            "normalized_label",
            name="uq_atlas_sector_label",
        ),
    )


class SectorCategoryRow(Base):
    __tablename__ = "atlas_sector_categories"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    sector_code: Mapped[str] = mapped_column(
        ForeignKey("atlas_sectors.code", ondelete="CASCADE"), index=True
    )
    name_en: Mapped[str] = mapped_column(String(255))
    name_tr: Mapped[str] = mapped_column(String(255))
    registry_version: Mapped[str] = mapped_column(String(64), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FactorSectorAssignmentRow(Base):
    """Derived business-sector projection; never replaces source taxonomy."""

    __tablename__ = "atlas_factor_sector_assignments"

    factor_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("atlas_factor_versions.id", ondelete="CASCADE"), primary_key=True
    )
    sector_code: Mapped[str] = mapped_column(ForeignKey("atlas_sectors.code"), index=True)
    category_code: Mapped[str] = mapped_column(
        ForeignKey("atlas_sector_categories.code"), index=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    derivation: Mapped[str] = mapped_column(String(64), default="verified_crosswalk")
    confidence: Mapped[int] = mapped_column(Integer)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    mapping_version: Mapped[str] = mapped_column(String(64), index=True)
    review_status: Mapped[str] = mapped_column(String(32), default="approved", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class UnitDefinitionRow(Base):
    __tablename__ = "atlas_unit_definitions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    dimension: Mapped[str] = mapped_column(String(128), index=True)
    scale_to_base: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    offset_to_base: Mapped[Decimal] = mapped_column(Numeric(38, 18), default=Decimal("0"))
    ucum_code: Mapped[str | None] = mapped_column(String(128))
    qualifiers: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list)
    registry_version: Mapped[str] = mapped_column(String(64), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class UnitAliasRow(Base):
    __tablename__ = "atlas_unit_aliases"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    unit_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("atlas_unit_definitions.id", ondelete="CASCADE"), index=True
    )
    alias: Mapped[str] = mapped_column(String(255))
    normalized_alias: Mapped[str] = mapped_column(String(255), index=True)
    source_code: Mapped[str | None] = mapped_column(String(64), index=True)
    language: Mapped[str | None] = mapped_column(String(8))
    review_status: Mapped[str] = mapped_column(String(32), default="approved")
    registry_version: Mapped[str] = mapped_column(String(64), index=True)

    __table_args__ = (
        UniqueConstraint("normalized_alias", "source_code", name="uq_atlas_unit_alias_source"),
    )


class FactorUnitExpressionRow(Base):
    __tablename__ = "atlas_factor_unit_expressions"

    factor_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("atlas_factor_versions.id", ondelete="CASCADE"), primary_key=True
    )
    numerator_code: Mapped[str | None] = mapped_column(String(128), index=True)
    denominator_code: Mapped[str | None] = mapped_column(String(128), index=True)
    denominator_quantity: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    parse_status: Mapped[str] = mapped_column(String(32), index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    registry_version: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class UnitExpressionMappingRow(Base):
    __tablename__ = "atlas_unit_expression_mappings"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    layer: Mapped[str] = mapped_column(String(32), index=True)
    raw_unit_hash: Mapped[str] = mapped_column(String(64))
    raw_unit: Mapped[str] = mapped_column(Text)
    normalized_expression: Mapped[str] = mapped_column(Text)
    mapping_status: Mapped[str] = mapped_column(String(32), index=True)
    canonical_expression: Mapped[str | None] = mapped_column(Text)
    numerator_code: Mapped[str | None] = mapped_column(String(128), index=True)
    denominator_code: Mapped[str | None] = mapped_column(String(128), index=True)
    denominator_quantity: Mapped[Decimal | None] = mapped_column(Numeric(38, 18))
    reason_code: Mapped[str] = mapped_column(String(128), index=True)
    registry_version: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    __table_args__ = (
        UniqueConstraint("layer", "raw_unit_hash", name="uq_atlas_unit_expression_layer_hash"),
    )


class ConceptRow(Base):
    __tablename__ = "atlas_concepts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    family: Mapped[str] = mapped_column(String(128), index=True)
    canonical_name_en: Mapped[str] = mapped_column(String(255))
    definition_en: Mapped[str | None] = mapped_column(Text)
    english_review_status: Mapped[str] = mapped_column(String(32), default="unreviewed", index=True)
    english_reviewed_by: Mapped[str | None] = mapped_column(String(255))
    english_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registry_version: Mapped[str] = mapped_column(String(64), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ConceptLabelRow(Base):
    __tablename__ = "atlas_concept_labels"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    concept_id: Mapped[UUID] = mapped_column(
        ForeignKey("atlas_concepts.id", ondelete="CASCADE"), index=True
    )
    language: Mapped[str] = mapped_column(String(8), index=True)
    locale: Mapped[str | None] = mapped_column(String(16), index=True)
    label: Mapped[str] = mapped_column(String(255))
    definition: Mapped[str | None] = mapped_column(Text)
    normalized_label: Mapped[str] = mapped_column(String(255), index=True)
    label_kind: Mapped[str] = mapped_column(String(32), index=True)
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    term_source: Mapped[str] = mapped_column(String(64), default="registry")
    translation_method: Mapped[str] = mapped_column(String(64))
    translation_model: Mapped[str | None] = mapped_column(String(255))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    review_status: Mapped[str] = mapped_column(String(32), index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(String(64), index=True)
    glossary_version: Mapped[str | None] = mapped_column(String(64), index=True)
    tokens: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list)
    transliteration: Mapped[str | None] = mapped_column(String(255), index=True)
    qa_flags: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list)
    supersedes_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("atlas_concept_labels.id", ondelete="SET NULL"), index=True
    )
    registry_version: Mapped[str] = mapped_column(String(64), index=True)

    __table_args__ = (
        UniqueConstraint(
            "concept_id",
            "language",
            "normalized_label",
            "review_status",
            name="uq_atlas_concept_label",
        ),
    )


class TranslationJobRow(Base):
    __tablename__ = "atlas_translation_jobs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    provider_job_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    input_file_id: Mapped[str | None] = mapped_column(String(255))
    output_file_id: Mapped[str | None] = mapped_column(String(255))
    error_file_id: Mapped[str | None] = mapped_column(String(255))
    source_language: Mapped[str] = mapped_column(String(8))
    target_language: Mapped[str] = mapped_column(String(8), index=True)
    model: Mapped[str] = mapped_column(String(255))
    qa_model: Mapped[str | None] = mapped_column(String(255))
    prompt_version: Mapped[str] = mapped_column(String(64), index=True)
    glossary_version: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True, default="created")
    requested_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    custom_ids: Mapped[dict[str, str]] = mapped_column(JSON_TYPE, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class GlossaryEntryRow(Base):
    __tablename__ = "atlas_translation_glossary"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_term: Mapped[str] = mapped_column(String(255), index=True)
    target_language: Mapped[str] = mapped_column(String(8), index=True)
    target_term: Mapped[str | None] = mapped_column(String(255))
    domain: Mapped[str] = mapped_column(String(128), default="environmental")
    protected: Mapped[bool] = mapped_column(Boolean, default=False)
    review_status: Mapped[str] = mapped_column(String(32), default="approved", index=True)
    version: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "source_term", "target_language", "domain", name="uq_atlas_translation_glossary"
        ),
    )


class FactorConceptRow(Base):
    __tablename__ = "atlas_factor_concepts"

    factor_id: Mapped[UUID] = mapped_column(
        ForeignKey("atlas_factors.id", ondelete="CASCADE"), primary_key=True
    )
    concept_id: Mapped[UUID] = mapped_column(
        ForeignKey("atlas_concepts.id", ondelete="CASCADE"), primary_key=True
    )
    relation: Mapped[str] = mapped_column(String(32), default="primary")
    mapping_version: Mapped[str] = mapped_column(String(64), index=True)
    review_status: Mapped[str] = mapped_column(String(32), default="approved")


class FactorApplicabilityRow(Base):
    """Derived serving projection; source facts remain on FactorVersionRow."""

    __tablename__ = "atlas_factor_applicabilities"

    factor_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("atlas_factor_versions.id", ondelete="CASCADE"), primary_key=True
    )
    concept_code: Mapped[str | None] = mapped_column(String(255), index=True)
    family_code: Mapped[str] = mapped_column(String(64), index=True)
    calculation_role: Mapped[str] = mapped_column(String(64), index=True)
    calculation_method: Mapped[str] = mapped_column(String(64), index=True)
    scope_category: Mapped[str | None] = mapped_column(String(32), index=True)
    scope3_categories: Mapped[list[int]] = mapped_column(JSON_TYPE, default=list)
    activity_basis: Mapped[str] = mapped_column(String(64), index=True)
    boundary: Mapped[str | None] = mapped_column(String(128), index=True)
    fallback_class: Mapped[str] = mapped_column(String(32), index=True)
    qualifiers: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    policy_version: Mapped[str] = mapped_column(String(64), index=True)
    review_status: Mapped[str] = mapped_column(String(32), index=True, default="projected")
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    __table_args__ = (
        Index(
            "ix_atlas_factor_applicabilities_policy_family",
            "policy_version",
            "family_code",
        ),
    )


class FactorRelationshipRow(Base):
    __tablename__ = "atlas_factor_relationships"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    from_factor_id: Mapped[UUID] = mapped_column(
        ForeignKey("atlas_factors.id", ondelete="CASCADE"), index=True
    )
    to_factor_id: Mapped[UUID] = mapped_column(
        ForeignKey("atlas_factors.id", ondelete="CASCADE"), index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(32), index=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    policy_version: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "from_factor_id",
            "to_factor_id",
            "relationship_type",
            name="uq_atlas_factor_relationship",
        ),
    )


class FallbackPolicyRow(Base):
    __tablename__ = "atlas_fallback_policies"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    country_code: Mapped[str] = mapped_column(String(2), index=True, default="*")
    calculation_profile: Mapped[str] = mapped_column(String(128), index=True)
    family_code: Mapped[str] = mapped_column(String(64), index=True)
    tier_code: Mapped[str] = mapped_column(String(32))
    tier_rank: Mapped[int] = mapped_column(Integer)
    proxy: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_acceptance: Mapped[bool] = mapped_column(Boolean, default=False)
    policy_version: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "calculation_profile",
            "country_code",
            "family_code",
            "tier_code",
            name="uq_atlas_fallback_policy_tier",
        ),
    )


class SourceMappingRow(Base):
    __tablename__ = "atlas_source_mappings"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("atlas_sources.id"), index=True)
    source_value: Mapped[str] = mapped_column(Text)
    taxonomy_code: Mapped[str] = mapped_column(String(255), index=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    version: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint(
            "source_id", "source_value", "version", name="uq_atlas_source_mapping_version"
        ),
    )


class QualityResultRow(Base):
    __tablename__ = "atlas_quality_results"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    dataset_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("atlas_dataset_versions.id"), index=True
    )
    rule_code: Mapped[str] = mapped_column(String(255), index=True)
    severity: Mapped[str] = mapped_column(String(32), index=True)
    message: Mapped[str] = mapped_column(Text)
    factor_logical_id: Mapped[str | None] = mapped_column(String(512))
    details: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ReviewRow(Base):
    __tablename__ = "atlas_review_queue"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    dataset_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("atlas_dataset_versions.id"), unique=True
    )
    status: Mapped[str] = mapped_column(String(32), index=True, default="pending")
    reasons: Mapped[list[str]] = mapped_column(JSON_TYPE, default=list)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(String(255))
    decision_note: Mapped[str | None] = mapped_column(Text)


class OutboxEventRow(Base):
    __tablename__ = "atlas_outbox_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE)
    status: Mapped[str] = mapped_column(String(32), index=True, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class FacilityRow(Base):
    __tablename__ = "atlas_facilities"

    code: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    country_code: Mapped[str] = mapped_column(ForeignKey("atlas_countries.code"), index=True)
    region: Mapped[str | None] = mapped_column(String(128), index=True)
    electricity_connection_level: Mapped[str | None] = mapped_column(String(32))
    industry_codes: Mapped[dict[str, str]] = mapped_column(JSON_TYPE, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    registry_version: Mapped[str] = mapped_column(String(64), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ConversionParameterRow(Base):
    __tablename__ = "atlas_conversion_parameters"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(24, 12))
    unit: Mapped[str] = mapped_column(String(128))
    source: Mapped[str] = mapped_column(Text)
    country_code: Mapped[str | None] = mapped_column(ForeignKey("atlas_countries.code"), index=True)
    facility_code: Mapped[str | None] = mapped_column(
        ForeignKey("atlas_facilities.code", ondelete="CASCADE"), index=True
    )
    valid_from: Mapped[date | None] = mapped_column(Date, index=True)
    valid_to: Mapped[date | None] = mapped_column(Date, index=True)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    review_status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(64), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class RegressionCaseRow(Base):
    __tablename__ = "atlas_regression_cases"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    suite_version: Mapped[str] = mapped_column(String(64), index=True)
    expected: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class RegressionRunRow(Base):
    __tablename__ = "atlas_regression_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    suite_version: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    total: Mapped[int] = mapped_column(Integer)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    changed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    requested_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RegressionResultRow(Base):
    __tablename__ = "atlas_regression_results"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("atlas_regression_runs.id", ondelete="CASCADE"), index=True
    )
    case_code: Mapped[str] = mapped_column(ForeignKey("atlas_regression_cases.code"), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    actual: Mapped[str] = mapped_column(Text)
    expected: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSON_TYPE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (UniqueConstraint("run_id", "case_code", name="uq_atlas_regression_run_case"),)


class RegressionReviewRow(Base):
    __tablename__ = "atlas_regression_reviews"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("atlas_regression_runs.id", ondelete="CASCADE"), unique=True
    )
    decision: Mapped[str] = mapped_column(String(32), index=True)
    reviewed_by: Mapped[str] = mapped_column(String(255))
    note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
