"""Separate source observations from curated factor versions.

Revision ID: 20260828_0009
Revises: 20260828_0008
Create Date: 2026-08-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260828_0009"
down_revision: str | None = "20260828_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_atlas_dataset_versions_supersedes_version_id
          ON atlas_dataset_versions (supersedes_version_id);
        CREATE INDEX IF NOT EXISTS ix_atlas_factor_versions_supersedes_version_id
          ON atlas_factor_versions (supersedes_version_id);

        CREATE TABLE IF NOT EXISTS atlas_source_observations (
          id UUID PRIMARY KEY,
          dataset_version_id UUID NOT NULL
            REFERENCES atlas_dataset_versions(id) ON DELETE CASCADE,
          raw_asset_id UUID NOT NULL REFERENCES atlas_raw_assets(id),
          observation_id VARCHAR(512) NOT NULL,
          entity_type VARCHAR(40) NOT NULL,
          name TEXT NOT NULL,
          value NUMERIC(38, 18) NOT NULL,
          unit VARCHAR(255) NOT NULL,
          reference_year INTEGER,
          gas VARCHAR(32),
          source_category TEXT,
          source_subcategory TEXT,
          source_coordinates JSONB NOT NULL DEFAULT '{}'::jsonb,
          attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT uq_atlas_source_observation_version
            UNIQUE (dataset_version_id, observation_id)
        );

        CREATE INDEX IF NOT EXISTS ix_atlas_source_observations_dataset_version_id
          ON atlas_source_observations (dataset_version_id);
        CREATE INDEX IF NOT EXISTS ix_atlas_source_observations_raw_asset_id
          ON atlas_source_observations (raw_asset_id);
        CREATE INDEX IF NOT EXISTS ix_atlas_source_observations_entity_type
          ON atlas_source_observations (entity_type);
        CREATE INDEX IF NOT EXISTS ix_atlas_source_observations_reference_year
          ON atlas_source_observations (reference_year);
        CREATE INDEX IF NOT EXISTS ix_atlas_source_observations_gas
          ON atlas_source_observations (gas);
        CREATE INDEX IF NOT EXISTS ix_atlas_source_observations_version_entity_year
          ON atlas_source_observations (dataset_version_id, entity_type, reference_year);

        INSERT INTO atlas_source_observations (
          id,
          dataset_version_id,
          raw_asset_id,
          observation_id,
          entity_type,
          name,
          value,
          unit,
          reference_year,
          gas,
          source_category,
          source_subcategory,
          source_coordinates,
          attributes,
          created_at
        )
        SELECT
          gen_random_uuid(),
          fv.dataset_version_id,
          p.raw_asset_id,
          fv.source_factor_id,
          fv.entity_type,
          fv.name,
          fv.factor_value,
          fv.factor_unit,
          fv.reference_year,
          fv.methodology->'details'->>'gas',
          fv.source_payload->>'source_category',
          fv.source_payload->>'source_subcategory',
          jsonb_build_object(
            'sheet', p.sheet,
            'table', p.table_name,
            'row', p.row_number,
            'parser_version', p.parser_version,
            'mapping_version', p.mapping_version
          ),
          jsonb_build_object(
            'migrated_from_factor_version_id', fv.id,
            'factor_value_kind', fv.factor_value_kind,
            'intended_use', fv.intended_use,
            'methodology', fv.methodology
          ),
          fv.created_at
        FROM atlas_factor_versions fv
        JOIN atlas_factors f ON f.id = fv.factor_id
        JOIN atlas_sources s ON s.id = f.source_id AND s.code = 'UNFCCC_TUIK'
        JOIN atlas_provenance p
          ON p.factor_version_id = fv.id AND p.role = 'total'
        ON CONFLICT (dataset_version_id, observation_id) DO NOTHING;

        UPDATE atlas_dataset_versions dv
        SET normalized_factor_count = 0,
            metrics = jsonb_set(
              jsonb_set(
                COALESCE(dv.metrics, '{}'::jsonb),
                '{source_observations}',
                to_jsonb(dv.parsed_row_count),
                true
              ),
              '{curated_factors}',
              '0'::jsonb,
              true
            )
        FROM atlas_datasets d
        JOIN atlas_sources s ON s.id = d.source_id
        WHERE dv.dataset_id = d.id AND s.code = 'UNFCCC_TUIK';

        DELETE FROM atlas_provenance p
        USING atlas_factor_versions fv, atlas_factors f, atlas_sources s
        WHERE p.factor_version_id = fv.id
          AND fv.factor_id = f.id
          AND f.source_id = s.id
          AND s.code = 'UNFCCC_TUIK';

        DELETE FROM atlas_factor_versions fv
        USING atlas_factors f, atlas_sources s
        WHERE fv.factor_id = f.id
          AND f.source_id = s.id
          AND s.code = 'UNFCCC_TUIK';

        DELETE FROM atlas_factors f
        USING atlas_sources s
        WHERE f.source_id = s.id
          AND s.code = 'UNFCCC_TUIK'
          AND NOT EXISTS (
            SELECT 1 FROM atlas_factor_versions fv WHERE fv.factor_id = f.id
          );
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "20260828_0009 is intentionally irreversible: dropping source observations "
        "would discard migrated audit history"
    )
