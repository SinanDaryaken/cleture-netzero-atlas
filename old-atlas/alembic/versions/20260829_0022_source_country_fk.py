"""Anchor source country identity to the central country registry.

Revision ID: 20260829_0022
Revises: 20260829_0021
Create Date: 2026-08-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260829_0022"
down_revision: str | None = "20260829_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_atlas_sources_country",
        "atlas_sources",
        "atlas_countries",
        ["country"],
        ["code"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_atlas_sources_country", "atlas_sources", type_="foreignkey")
