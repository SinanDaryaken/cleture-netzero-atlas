"""Add auditable concept-label review decisions.

Revision ID: 20260828_0015
Revises: 20260828_0014
Create Date: 2026-08-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260828_0015"
down_revision: str | None = "20260828_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE atlas_concept_labels ADD COLUMN reviewed_by VARCHAR(255);
        ALTER TABLE atlas_concept_labels ADD COLUMN reviewed_at TIMESTAMPTZ;
        ALTER TABLE atlas_concept_labels ADD COLUMN review_note TEXT;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE atlas_concept_labels DROP COLUMN IF EXISTS review_note;
        ALTER TABLE atlas_concept_labels DROP COLUMN IF EXISTS reviewed_at;
        ALTER TABLE atlas_concept_labels DROP COLUMN IF EXISTS reviewed_by;
        """
    )
