"""Separate factor geography origin from applicability.

Revision ID: 20260827_0002
Revises: 20260827_0001
"""

from alembic import op

revision = "20260827_0002"
down_revision = "20260827_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS supports a clean database created from the current model snapshot.
    op.execute(
        """
        ALTER TABLE atlas_factor_versions
          ADD COLUMN IF NOT EXISTS origin_geography JSONB,
          ADD COLUMN IF NOT EXISTS applicable_geographies JSONB NOT NULL DEFAULT '[]'::jsonb,
          ADD COLUMN IF NOT EXISTS geography_type VARCHAR(32) NOT NULL DEFAULT 'proxy'
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'atlas_factor_versions' AND column_name = 'geography'
          ) THEN
            UPDATE atlas_factor_versions AS fv
            SET
              origin_geography = CASE
                WHEN source.code = 'DEFRA'
                  THEN jsonb_build_object(
                    'level', 'country', 'code', 'GB', 'name', 'United Kingdom'
                  )
                ELSE NULL
              END,
              applicable_geographies = CASE
                WHEN source.code = 'DEFRA'
                  THEN jsonb_build_array(
                    jsonb_build_object(
                      'level', 'country', 'code', 'GB', 'name', 'United Kingdom'
                    )
                  )
                WHEN fv.geography IS NOT NULL AND fv.geography <> '{}'::jsonb
                  THEN jsonb_build_array(fv.geography)
                ELSE '[]'::jsonb
              END,
              geography_type = CASE
                WHEN source.code = 'DEFRA' THEN 'country_specific'
                WHEN fv.geography->>'level' = 'global' THEN 'global'
                ELSE 'proxy'
              END
            FROM atlas_factors AS factor
            JOIN atlas_sources AS source ON source.id = factor.source_id
            WHERE factor.id = fv.factor_id;

            ALTER TABLE atlas_factor_versions DROP COLUMN geography;
          END IF;
        END $$
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_atlas_factor_versions_geography_type
        ON atlas_factor_versions (geography_type)
        """
    )
    op.execute(
        """
        ALTER TABLE atlas_factor_versions
          ALTER COLUMN applicable_geographies DROP DEFAULT,
          ALTER COLUMN geography_type DROP DEFAULT
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE atlas_factor_versions
          ADD COLUMN IF NOT EXISTS geography JSONB NOT NULL DEFAULT '{}'::jsonb
        """
    )
    op.execute(
        """
        UPDATE atlas_factor_versions
        SET geography = COALESCE(applicable_geographies->0, '{}'::jsonb)
        """
    )
    op.execute("DROP INDEX IF EXISTS ix_atlas_factor_versions_geography_type")
    op.execute(
        """
        ALTER TABLE atlas_factor_versions
          DROP COLUMN IF EXISTS origin_geography,
          DROP COLUMN IF EXISTS applicable_geographies,
          DROP COLUMN IF EXISTS geography_type
        """
    )
