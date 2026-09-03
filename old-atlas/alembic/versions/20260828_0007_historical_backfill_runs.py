"""Add targeted historical backfill runs.

Revision ID: 20260828_0007
Revises: 20260827_0006
Create Date: 2026-08-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260828_0007"
down_revision: str | None = "20260827_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE atlas_source_runs
          ADD COLUMN IF NOT EXISTS run_mode VARCHAR(32) NOT NULL DEFAULT 'latest',
          ADD COLUMN IF NOT EXISTS requested_reference_year INTEGER;

        ALTER TABLE atlas_source_runs
          DROP CONSTRAINT IF EXISTS ck_atlas_source_runs_mode_target;
        ALTER TABLE atlas_source_runs
          ADD CONSTRAINT ck_atlas_source_runs_mode_target CHECK (
            (run_mode = 'latest' AND requested_reference_year IS NULL)
            OR
            (run_mode = 'historical_backfill' AND requested_reference_year IS NOT NULL)
          );

        CREATE INDEX IF NOT EXISTS ix_atlas_source_runs_history_target
          ON atlas_source_runs (source_id, requested_reference_year, created_at);

        ALTER TABLE atlas_source_runs ALTER COLUMN run_mode DROP DEFAULT;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS ix_atlas_source_runs_history_target;
        ALTER TABLE atlas_source_runs
          DROP CONSTRAINT IF EXISTS ck_atlas_source_runs_mode_target,
          DROP COLUMN IF EXISTS requested_reference_year,
          DROP COLUMN IF EXISTS run_mode;
        """
    )
