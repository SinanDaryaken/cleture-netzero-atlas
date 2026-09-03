"""Add factor semantics and dataset metrics.

Revision ID: 20260827_0003
Revises: 20260827_0002
"""

from alembic import op

revision = "20260827_0003"
down_revision = "20260827_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Defaults make this safe both for an upgraded database and a clean database
    # whose tables were created from the current SQLAlchemy metadata snapshot.
    op.execute(
        """
        ALTER TABLE atlas_dataset_versions
          ADD COLUMN IF NOT EXISTS metrics JSONB NOT NULL DEFAULT '{}'::jsonb;

        ALTER TABLE atlas_factor_versions
          ADD COLUMN IF NOT EXISTS factor_value_kind VARCHAR(32)
            NOT NULL DEFAULT 'co2e_total',
          ADD COLUMN IF NOT EXISTS intended_use VARCHAR(32)
            NOT NULL DEFAULT 'inventory';

        CREATE INDEX IF NOT EXISTS ix_atlas_factor_versions_factor_value_kind
          ON atlas_factor_versions (factor_value_kind);
        CREATE INDEX IF NOT EXISTS ix_atlas_factor_versions_intended_use
          ON atlas_factor_versions (intended_use);

        ALTER TABLE atlas_dataset_versions ALTER COLUMN metrics DROP DEFAULT;
        ALTER TABLE atlas_factor_versions ALTER COLUMN factor_value_kind DROP DEFAULT;
        ALTER TABLE atlas_factor_versions ALTER COLUMN intended_use DROP DEFAULT;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS ix_atlas_factor_versions_intended_use;
        DROP INDEX IF EXISTS ix_atlas_factor_versions_factor_value_kind;
        ALTER TABLE atlas_factor_versions
          DROP COLUMN IF EXISTS intended_use,
          DROP COLUMN IF EXISTS factor_value_kind;
        ALTER TABLE atlas_dataset_versions DROP COLUMN IF EXISTS metrics;
        """
    )
