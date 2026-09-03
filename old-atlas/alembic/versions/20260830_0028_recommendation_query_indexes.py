"""Index the recommendation serving path by geography and policy family.

Revision ID: 20260830_0028
Revises: 20260830_0027
Create Date: 2026-08-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260830_0028"
down_revision: str | None = "20260830_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX ix_atlas_factor_versions_applicable_geographies
          ON atlas_factor_versions
          USING gin (applicable_geographies jsonb_path_ops);

        CREATE INDEX ix_atlas_factor_applicabilities_policy_family
          ON atlas_factor_applicabilities (policy_version, family_code);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS ix_atlas_factor_applicabilities_policy_family;
        DROP INDEX IF EXISTS ix_atlas_factor_versions_applicable_geographies;
        """
    )
