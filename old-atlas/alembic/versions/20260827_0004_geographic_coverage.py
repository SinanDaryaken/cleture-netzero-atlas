"""Add geographic coverage semantics.

Revision ID: 20260827_0004
Revises: 20260827_0003
"""

from alembic import op

revision = "20260827_0004"
down_revision = "20260827_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE atlas_factor_versions
          ADD COLUMN IF NOT EXISTS geography_level VARCHAR(32)
            NOT NULL DEFAULT 'country',
          ADD COLUMN IF NOT EXISTS geographic_specificity INTEGER
            NOT NULL DEFAULT 3,
          ADD COLUMN IF NOT EXISTS geographic_fit_type VARCHAR(32)
            NOT NULL DEFAULT 'proxy';

        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'atlas_factor_versions' AND column_name = 'geography_type'
          ) THEN
            UPDATE atlas_factor_versions
            SET
              geography_level = COALESCE(
                (
                  SELECT item->>'level'
                  FROM jsonb_array_elements(applicable_geographies) AS item
                  ORDER BY CASE item->>'level'
                    WHEN 'global' THEN 0
                    WHEN 'continent' THEN 1
                    WHEN 'region' THEN 2
                    WHEN 'country' THEN 3
                    WHEN 'state' THEN 4
                    WHEN 'province' THEN 4
                    WHEN 'city' THEN 5
                    WHEN 'grid' THEN 6
                    ELSE 2
                  END DESC
                  LIMIT 1
                ),
                CASE geography_type
                  WHEN 'global' THEN 'global'
                  WHEN 'regional' THEN 'region'
                  ELSE 'country'
                END
              ),
              geographic_specificity = COALESCE(
                (
                  SELECT max(CASE item->>'level'
                    WHEN 'global' THEN 0
                    WHEN 'continent' THEN 1
                    WHEN 'region' THEN 2
                    WHEN 'country' THEN 3
                    WHEN 'state' THEN 4
                    WHEN 'province' THEN 4
                    WHEN 'city' THEN 5
                    WHEN 'grid' THEN 6
                    ELSE 2
                  END)
                  FROM jsonb_array_elements(applicable_geographies) AS item
                ),
                CASE geography_type WHEN 'global' THEN 0 ELSE 3 END
              ),
              geographic_fit_type = geography_type;

            DROP INDEX IF EXISTS ix_atlas_factor_versions_geography_type;
            ALTER TABLE atlas_factor_versions DROP COLUMN geography_type;
          END IF;
        END $$;

        CREATE INDEX IF NOT EXISTS ix_atlas_factor_versions_geography_level
          ON atlas_factor_versions (geography_level);
        CREATE INDEX IF NOT EXISTS ix_atlas_factor_versions_geographic_specificity
          ON atlas_factor_versions (geographic_specificity);
        CREATE INDEX IF NOT EXISTS ix_atlas_factor_versions_geographic_fit_type
          ON atlas_factor_versions (geographic_fit_type);

        ALTER TABLE atlas_factor_versions ALTER COLUMN geography_level DROP DEFAULT;
        ALTER TABLE atlas_factor_versions ALTER COLUMN geographic_specificity DROP DEFAULT;
        ALTER TABLE atlas_factor_versions ALTER COLUMN geographic_fit_type DROP DEFAULT;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE atlas_factor_versions
          ADD COLUMN IF NOT EXISTS geography_type VARCHAR(32)
            NOT NULL DEFAULT 'proxy';
        UPDATE atlas_factor_versions SET geography_type = geographic_fit_type;
        CREATE INDEX IF NOT EXISTS ix_atlas_factor_versions_geography_type
          ON atlas_factor_versions (geography_type);
        DROP INDEX IF EXISTS ix_atlas_factor_versions_geographic_fit_type;
        DROP INDEX IF EXISTS ix_atlas_factor_versions_geographic_specificity;
        DROP INDEX IF EXISTS ix_atlas_factor_versions_geography_level;
        ALTER TABLE atlas_factor_versions
          DROP COLUMN IF EXISTS geographic_fit_type,
          DROP COLUMN IF EXISTS geographic_specificity,
          DROP COLUMN IF EXISTS geography_level;
        ALTER TABLE atlas_factor_versions ALTER COLUMN geography_type DROP DEFAULT;
        """
    )
