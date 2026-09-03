"""Add category-aware Scope 3 regression cases.

Revision ID: 20260830_0026
Revises: 20260830_0025
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_0026"
down_revision: str | None = "20260830_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUITE_VERSION = "2026.08.30.2"
SCOPE3_CASES = (
    ("TC-000059", "Scope 3 category catalog"),
    ("TC-000060", "Scope 3 category 1 purchased services"),
    ("TC-000061", "Scope 3 category 3 fuel and energy"),
    ("TC-000062", "Scope 3 category 4 upstream freight"),
    ("TC-000063", "Scope 3 category 5 operational waste"),
    ("TC-000064", "Scope 3 category 6 business travel"),
    ("TC-000065", "Scope 3 freight direction requires category"),
    ("TC-000066", "Scope 3 category 9 downstream freight"),
    ("TC-000067", "Scope 3 category 12 sold-product end of life"),
    ("TC-000068", "Scope 3 category 15 coverage gap"),
)


def upgrade() -> None:
    cases = sa.table(
        "atlas_regression_cases",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("suite_version", sa.String()),
        sa.column("expected", sa.JSON()),
        sa.column("metadata_json", sa.JSON()),
        sa.column("active", sa.Boolean()),
    )
    op.execute(
        cases.update()
        .where(cases.c.code.in_(tuple(f"TC-{index:06d}" for index in range(1, 59))))
        .values(suite_version=SUITE_VERSION)
    )
    op.bulk_insert(
        cases,
        [
            {
                "code": code,
                "name": name,
                "suite_version": SUITE_VERSION,
                "expected": {},
                "metadata_json": {"contract": "ghg-protocol-scope3-categories"},
                "active": True,
            }
            for code, name in SCOPE3_CASES
        ],
    )


def downgrade() -> None:
    cases = sa.table(
        "atlas_regression_cases",
        sa.column("code", sa.String()),
        sa.column("suite_version", sa.String()),
    )
    op.execute(cases.delete().where(cases.c.code.in_(tuple(code for code, _ in SCOPE3_CASES))))
    op.execute(
        cases.update()
        .where(cases.c.code.in_(tuple(f"TC-{index:06d}" for index in range(1, 59))))
        .values(suite_version="2026.08.30.1")
    )
