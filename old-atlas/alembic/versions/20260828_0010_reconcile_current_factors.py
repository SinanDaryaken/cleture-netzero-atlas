"""Close stale current factors removed by a newer source snapshot.

Revision ID: 20260828_0010
Revises: 20260828_0009
Create Date: 2026-08-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260828_0010"
down_revision: str | None = "20260828_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        WITH latest_snapshot AS (
          SELECT DISTINCT ON (f.source_id, fv.reference_year)
            f.source_id,
            fv.reference_year,
            fv.dataset_version_id
          FROM atlas_factor_versions fv
          JOIN atlas_factors f ON f.id = fv.factor_id
          JOIN atlas_dataset_versions dv ON dv.id = fv.dataset_version_id
          WHERE dv.status = 'published'
            AND fv.reference_year IS NOT NULL
          ORDER BY
            f.source_id,
            fv.reference_year,
            dv.release_year DESC NULLS LAST,
            dv.published_at DESC NULLS LAST,
            dv.system_effective_from DESC NULLS LAST
        )
        UPDATE atlas_factor_versions stale
        SET version_status = 'superseded',
            system_effective_to = COALESCE(stale.system_effective_to, now()),
            superseded_at = COALESCE(stale.superseded_at, now())
        FROM atlas_factors f, latest_snapshot latest
        WHERE stale.factor_id = f.id
          AND latest.source_id = f.source_id
          AND latest.reference_year = stale.reference_year
          AND stale.version_status = 'current'
          AND stale.dataset_version_id <> latest.dataset_version_id;
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "20260828_0010 is intentionally irreversible: reopening stale factor periods "
        "would corrupt system-time history"
    )
