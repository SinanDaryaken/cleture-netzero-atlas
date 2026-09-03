"""Increase factor value precision for source parameters.

Revision ID: 20260827_0005
Revises: 20260827_0004
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260827_0005"
down_revision: str | None = "20260827_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "atlas_factor_versions",
        "factor_value",
        existing_type=sa.Numeric(30, 12),
        type_=sa.Numeric(38, 18),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "atlas_factor_versions",
        "factor_value",
        existing_type=sa.Numeric(38, 18),
        type_=sa.Numeric(30, 12),
        existing_nullable=False,
    )
