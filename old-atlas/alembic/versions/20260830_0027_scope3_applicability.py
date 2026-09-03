"""Persist Scope 3 category applicability on the serving projection.

Revision ID: 20260830_0027
Revises: 20260830_0026
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260830_0027"
down_revision: str | None = "20260830_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "atlas_factor_applicabilities",
        sa.Column(
            "scope3_categories",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("atlas_factor_applicabilities", "scope3_categories")
