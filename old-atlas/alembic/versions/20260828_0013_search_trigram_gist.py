"""Add KNN trigram index for low-latency fuzzy factor search.

Revision ID: 20260828_0013
Revises: 20260828_0012
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260828_0013"
down_revision: str | None = "20260828_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX ix_atlas_factor_versions_name_trgm_gist
          ON atlas_factor_versions USING gist (name gist_trgm_ops(siglen=256));
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_atlas_factor_versions_name_trgm_gist")
