"""Add the global Scope 1 and Scope 2 facility baseline cases.

Revision ID: 20260830_0025
Revises: 20260830_0024
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_0025"
down_revision: str | None = "20260830_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUITE_VERSION = "2026.08.30.1"
BASELINE_CASES = tuple(
    (
        f"TC-{case_number:06d}",
        f"{facility_code} {label}",
    )
    for facility_number in range(1, 21)
    for case_number, facility_code, label in (
        (
            19 + ((facility_number - 1) * 2),
            f"FAC-{facility_number:03d}",
            "Scope 1 natural gas",
        ),
        (
            20 + ((facility_number - 1) * 2),
            f"FAC-{facility_number:03d}",
            "Scope 2 electricity",
        ),
    )
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
        .where(cases.c.code.in_(tuple(f"TC-{index:06d}" for index in range(1, 19))))
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
                "metadata_json": {"baseline": "global-facility-scope1-scope2"},
                "active": True,
            }
            for code, name in BASELINE_CASES
        ],
    )


def downgrade() -> None:
    cases = sa.table(
        "atlas_regression_cases",
        sa.column("code", sa.String()),
        sa.column("suite_version", sa.String()),
    )
    op.execute(cases.delete().where(cases.c.code.in_(tuple(code for code, _ in BASELINE_CASES))))
    op.execute(
        cases.update()
        .where(cases.c.code.in_(tuple(f"TC-{index:06d}" for index in range(1, 19))))
        .values(suite_version="2026.08.30")
    )
