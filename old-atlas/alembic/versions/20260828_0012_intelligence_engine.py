"""Add unit, concept, and PostgreSQL lexical-search intelligence structures.

Revision ID: 20260828_0012
Revises: 20260828_0011
Create Date: 2026-08-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260828_0012"
down_revision: str | None = "20260828_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE EXTENSION IF NOT EXISTS pg_trgm;

        CREATE TABLE atlas_unit_definitions (
          id UUID PRIMARY KEY,
          code VARCHAR(128) NOT NULL UNIQUE,
          dimension VARCHAR(128) NOT NULL,
          scale_to_base NUMERIC(38, 18) NOT NULL,
          offset_to_base NUMERIC(38, 18) NOT NULL DEFAULT 0,
          ucum_code VARCHAR(128),
          qualifiers JSONB NOT NULL DEFAULT '[]'::jsonb,
          registry_version VARCHAR(64) NOT NULL,
          active BOOLEAN NOT NULL DEFAULT TRUE
        );
        CREATE INDEX ix_atlas_unit_definitions_code ON atlas_unit_definitions (code);
        CREATE INDEX ix_atlas_unit_definitions_dimension ON atlas_unit_definitions (dimension);
        CREATE INDEX ix_atlas_unit_definitions_registry_version
          ON atlas_unit_definitions (registry_version);

        CREATE TABLE atlas_unit_aliases (
          id UUID PRIMARY KEY,
          unit_definition_id UUID NOT NULL REFERENCES atlas_unit_definitions(id) ON DELETE CASCADE,
          alias VARCHAR(255) NOT NULL,
          normalized_alias VARCHAR(255) NOT NULL,
          source_code VARCHAR(64),
          language VARCHAR(8),
          review_status VARCHAR(32) NOT NULL DEFAULT 'approved',
          registry_version VARCHAR(64) NOT NULL,
          CONSTRAINT uq_atlas_unit_alias_source UNIQUE NULLS NOT DISTINCT
            (normalized_alias, source_code)
        );
        CREATE INDEX ix_atlas_unit_aliases_unit_definition_id
          ON atlas_unit_aliases (unit_definition_id);
        CREATE INDEX ix_atlas_unit_aliases_normalized_alias
          ON atlas_unit_aliases (normalized_alias);
        CREATE INDEX ix_atlas_unit_aliases_source_code ON atlas_unit_aliases (source_code);
        CREATE INDEX ix_atlas_unit_aliases_registry_version
          ON atlas_unit_aliases (registry_version);

        CREATE TABLE atlas_factor_unit_expressions (
          factor_version_id UUID PRIMARY KEY
            REFERENCES atlas_factor_versions(id) ON DELETE CASCADE,
          numerator_code VARCHAR(128),
          denominator_code VARCHAR(128),
          denominator_quantity NUMERIC(38, 18),
          parse_status VARCHAR(32) NOT NULL,
          reason TEXT,
          registry_version VARCHAR(64) NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_atlas_factor_unit_expressions_numerator_code
          ON atlas_factor_unit_expressions (numerator_code);
        CREATE INDEX ix_atlas_factor_unit_expressions_denominator_code
          ON atlas_factor_unit_expressions (denominator_code);
        CREATE INDEX ix_atlas_factor_unit_expressions_parse_status
          ON atlas_factor_unit_expressions (parse_status);
        CREATE INDEX ix_atlas_factor_unit_expressions_registry_version
          ON atlas_factor_unit_expressions (registry_version);

        CREATE TABLE atlas_concepts (
          id UUID PRIMARY KEY,
          code VARCHAR(255) NOT NULL UNIQUE,
          family VARCHAR(128) NOT NULL,
          canonical_name_en VARCHAR(255) NOT NULL,
          registry_version VARCHAR(64) NOT NULL,
          active BOOLEAN NOT NULL DEFAULT TRUE
        );
        CREATE INDEX ix_atlas_concepts_code ON atlas_concepts (code);
        CREATE INDEX ix_atlas_concepts_family ON atlas_concepts (family);
        CREATE INDEX ix_atlas_concepts_registry_version ON atlas_concepts (registry_version);

        CREATE TABLE atlas_concept_labels (
          id UUID PRIMARY KEY,
          concept_id UUID NOT NULL REFERENCES atlas_concepts(id) ON DELETE CASCADE,
          language VARCHAR(8) NOT NULL,
          label VARCHAR(255) NOT NULL,
          normalized_label VARCHAR(255) NOT NULL,
          label_kind VARCHAR(32) NOT NULL,
          translation_method VARCHAR(64) NOT NULL,
          translation_model VARCHAR(255),
          confidence NUMERIC(8, 6),
          review_status VARCHAR(32) NOT NULL,
          registry_version VARCHAR(64) NOT NULL,
          CONSTRAINT uq_atlas_concept_label UNIQUE (concept_id, language, normalized_label)
        );
        CREATE INDEX ix_atlas_concept_labels_concept_id ON atlas_concept_labels (concept_id);
        CREATE INDEX ix_atlas_concept_labels_language ON atlas_concept_labels (language);
        CREATE INDEX ix_atlas_concept_labels_normalized_label
          ON atlas_concept_labels (normalized_label);
        CREATE INDEX ix_atlas_concept_labels_label_kind ON atlas_concept_labels (label_kind);
        CREATE INDEX ix_atlas_concept_labels_review_status
          ON atlas_concept_labels (review_status);
        CREATE INDEX ix_atlas_concept_labels_registry_version
          ON atlas_concept_labels (registry_version);
        CREATE INDEX ix_atlas_concept_labels_trgm
          ON atlas_concept_labels USING gin (normalized_label gin_trgm_ops);

        CREATE TABLE atlas_factor_concepts (
          factor_id UUID NOT NULL REFERENCES atlas_factors(id) ON DELETE CASCADE,
          concept_id UUID NOT NULL REFERENCES atlas_concepts(id) ON DELETE CASCADE,
          relation VARCHAR(32) NOT NULL DEFAULT 'primary',
          mapping_version VARCHAR(64) NOT NULL,
          review_status VARCHAR(32) NOT NULL DEFAULT 'approved',
          PRIMARY KEY (factor_id, concept_id)
        );
        CREATE INDEX ix_atlas_factor_concepts_mapping_version
          ON atlas_factor_concepts (mapping_version);

        CREATE INDEX ix_atlas_factor_versions_search_fts
          ON atlas_factor_versions USING gin (
            to_tsvector(
              'simple',
              coalesce(name, '') || ' ' || coalesce(description, '') || ' ' ||
              coalesce(taxonomy_code, '') || ' ' || coalesce(activity_type, '')
            )
          );
        CREATE INDEX ix_atlas_factor_versions_name_trgm
          ON atlas_factor_versions USING gin (name gin_trgm_ops);
        CREATE INDEX ix_atlas_factor_versions_taxonomy_trgm
          ON atlas_factor_versions USING gin (taxonomy_code gin_trgm_ops);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS ix_atlas_factor_versions_taxonomy_trgm;
        DROP INDEX IF EXISTS ix_atlas_factor_versions_name_trgm;
        DROP INDEX IF EXISTS ix_atlas_factor_versions_search_fts;
        DROP TABLE IF EXISTS atlas_factor_concepts;
        DROP TABLE IF EXISTS atlas_concept_labels;
        DROP TABLE IF EXISTS atlas_concepts;
        DROP TABLE IF EXISTS atlas_factor_unit_expressions;
        DROP TABLE IF EXISTS atlas_unit_aliases;
        DROP TABLE IF EXISTS atlas_unit_definitions;
        """
    )
