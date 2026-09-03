"""Add spreadsheet column coordinates to factor provenance.

Revision ID: 20260828_0011
Revises: 20260828_0010
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260828_0011"
down_revision: str | None = "20260828_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("atlas_provenance", sa.Column("column_number", sa.Integer(), nullable=True))
    op.add_column("atlas_provenance", sa.Column("column_name", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("atlas_provenance", "column_name")
    op.drop_column("atlas_provenance", "column_number")
