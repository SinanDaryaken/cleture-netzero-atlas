"""Add environmental entity semantics to canonical records.

Revision ID: 20260828_0008
Revises: 20260828_0007
Create Date: 2026-08-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260828_0008"
down_revision: str | None = "20260828_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE atlas_factor_versions
          ADD COLUMN IF NOT EXISTS entity_type VARCHAR(40)
          NOT NULL DEFAULT 'emission_factor';

        CREATE INDEX IF NOT EXISTS ix_atlas_factor_versions_entity_type
          ON atlas_factor_versions (entity_type);

        ALTER TABLE atlas_factor_versions ALTER COLUMN entity_type DROP DEFAULT;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS ix_atlas_factor_versions_entity_type;
        ALTER TABLE atlas_factor_versions DROP COLUMN IF EXISTS entity_type;
        """
    )
