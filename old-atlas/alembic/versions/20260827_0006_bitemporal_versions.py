"""Add bitemporal dataset and factor version semantics.

Revision ID: 20260827_0006
Revises: 20260827_0005
Create Date: 2026-08-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260827_0006"
down_revision: str | None = "20260827_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE atlas_dataset_versions
          ADD COLUMN IF NOT EXISTS valid_from DATE,
          ADD COLUMN IF NOT EXISTS valid_to DATE,
          ADD COLUMN IF NOT EXISTS source_published_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS retrieved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          ADD COLUMN IF NOT EXISTS system_effective_from TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS system_effective_to TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS superseded_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS supersedes_version_id UUID,
          ADD COLUMN IF NOT EXISTS version_status VARCHAR(32) NOT NULL DEFAULT 'candidate';

        ALTER TABLE atlas_factor_versions
          ADD COLUMN IF NOT EXISTS valid_from DATE,
          ADD COLUMN IF NOT EXISTS valid_to DATE,
          ADD COLUMN IF NOT EXISTS source_published_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS retrieved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          ADD COLUMN IF NOT EXISTS system_effective_from TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS system_effective_to TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS superseded_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS supersedes_version_id UUID,
          ADD COLUMN IF NOT EXISTS version_status VARCHAR(32) NOT NULL DEFAULT 'candidate';
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'fk_dataset_version_supersedes'
          ) THEN
            ALTER TABLE atlas_dataset_versions
              ADD CONSTRAINT fk_dataset_version_supersedes
              FOREIGN KEY (supersedes_version_id) REFERENCES atlas_dataset_versions(id);
          END IF;
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'fk_factor_version_supersedes'
          ) THEN
            ALTER TABLE atlas_factor_versions
              ADD CONSTRAINT fk_factor_version_supersedes
              FOREIGN KEY (supersedes_version_id) REFERENCES atlas_factor_versions(id);
          END IF;
        END $$;
        """
    )
    op.execute(
        """
        UPDATE atlas_dataset_versions AS version
        SET
          valid_from = CASE
            WHEN release_year IS NULL THEN NULL
            ELSE make_date(release_year, 1, 1)
          END,
          valid_to = CASE
            WHEN release_year IS NULL THEN NULL
            ELSE make_date(release_year + 1, 1, 1)
          END,
          retrieved_at = COALESCE(
            (
              SELECT raw.downloaded_at
              FROM atlas_raw_assets AS raw
              WHERE raw.id = version.raw_asset_id
            ),
            version.created_at
          ),
          system_effective_from = CASE
            WHEN version.status = 'published'
              THEN COALESCE(version.published_at, version.created_at)
            ELSE NULL
          END,
          version_status = CASE
            WHEN version.status = 'rejected' THEN 'rejected'
            WHEN dataset.current_version_id = version.id THEN 'current'
            WHEN version.status = 'published' THEN 'superseded'
            ELSE 'candidate'
          END
        FROM atlas_datasets AS dataset
        WHERE dataset.id = version.dataset_id;

        UPDATE atlas_factor_versions AS factor_version
        SET
          valid_from = CASE
            WHEN factor_version.reference_year IS NULL THEN NULL
            ELSE make_date(factor_version.reference_year, 1, 1)
          END,
          valid_to = CASE
            WHEN factor_version.reference_year IS NULL THEN NULL
            ELSE make_date(factor_version.reference_year + 1, 1, 1)
          END,
          source_published_at = dataset_version.source_published_at,
          retrieved_at = dataset_version.retrieved_at,
          system_effective_from = dataset_version.system_effective_from,
          version_status = dataset_version.version_status
        FROM atlas_dataset_versions AS dataset_version
        WHERE dataset_version.id = factor_version.dataset_version_id;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_atlas_dataset_versions_version_status
          ON atlas_dataset_versions (version_status);
        CREATE INDEX IF NOT EXISTS ix_atlas_dataset_versions_system_effective_from
          ON atlas_dataset_versions (system_effective_from);
        CREATE INDEX IF NOT EXISTS ix_atlas_dataset_versions_system_effective_to
          ON atlas_dataset_versions (system_effective_to);
        CREATE INDEX IF NOT EXISTS ix_atlas_factor_versions_version_status
          ON atlas_factor_versions (version_status);
        CREATE INDEX IF NOT EXISTS ix_atlas_factor_versions_valid_from
          ON atlas_factor_versions (valid_from);
        CREATE INDEX IF NOT EXISTS ix_atlas_factor_versions_valid_to
          ON atlas_factor_versions (valid_to);
        CREATE INDEX IF NOT EXISTS ix_atlas_factor_versions_system_effective_from
          ON atlas_factor_versions (system_effective_from);
        CREATE INDEX IF NOT EXISTS ix_atlas_factor_versions_system_effective_to
          ON atlas_factor_versions (system_effective_to);

        CREATE UNIQUE INDEX IF NOT EXISTS uq_atlas_dataset_current_release
          ON atlas_dataset_versions (dataset_id, COALESCE(release_year, -1))
          WHERE version_status = 'current';
        CREATE UNIQUE INDEX IF NOT EXISTS uq_atlas_factor_current_temporal
          ON atlas_factor_versions (
            factor_id,
            COALESCE(reference_year, -1),
            COALESCE(valid_from, DATE '-infinity'),
            COALESCE(valid_to, DATE 'infinity')
          )
          WHERE version_status = 'current';

        ALTER TABLE atlas_dataset_versions ALTER COLUMN retrieved_at DROP DEFAULT;
        ALTER TABLE atlas_dataset_versions ALTER COLUMN version_status DROP DEFAULT;
        ALTER TABLE atlas_factor_versions ALTER COLUMN retrieved_at DROP DEFAULT;
        ALTER TABLE atlas_factor_versions ALTER COLUMN version_status DROP DEFAULT;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS uq_atlas_factor_current_temporal;
        DROP INDEX IF EXISTS uq_atlas_dataset_current_release;
        DROP INDEX IF EXISTS ix_atlas_factor_versions_system_effective_to;
        DROP INDEX IF EXISTS ix_atlas_factor_versions_system_effective_from;
        DROP INDEX IF EXISTS ix_atlas_factor_versions_valid_to;
        DROP INDEX IF EXISTS ix_atlas_factor_versions_valid_from;
        DROP INDEX IF EXISTS ix_atlas_factor_versions_version_status;
        DROP INDEX IF EXISTS ix_atlas_dataset_versions_system_effective_to;
        DROP INDEX IF EXISTS ix_atlas_dataset_versions_system_effective_from;
        DROP INDEX IF EXISTS ix_atlas_dataset_versions_version_status;

        ALTER TABLE atlas_factor_versions
          DROP CONSTRAINT IF EXISTS fk_factor_version_supersedes,
          DROP COLUMN IF EXISTS version_status,
          DROP COLUMN IF EXISTS supersedes_version_id,
          DROP COLUMN IF EXISTS superseded_at,
          DROP COLUMN IF EXISTS system_effective_to,
          DROP COLUMN IF EXISTS system_effective_from,
          DROP COLUMN IF EXISTS retrieved_at,
          DROP COLUMN IF EXISTS source_published_at,
          DROP COLUMN IF EXISTS valid_to,
          DROP COLUMN IF EXISTS valid_from;

        ALTER TABLE atlas_dataset_versions
          DROP CONSTRAINT IF EXISTS fk_dataset_version_supersedes,
          DROP COLUMN IF EXISTS version_status,
          DROP COLUMN IF EXISTS supersedes_version_id,
          DROP COLUMN IF EXISTS superseded_at,
          DROP COLUMN IF EXISTS system_effective_to,
          DROP COLUMN IF EXISTS system_effective_from,
          DROP COLUMN IF EXISTS retrieved_at,
          DROP COLUMN IF EXISTS source_published_at,
          DROP COLUMN IF EXISTS valid_to,
          DROP COLUMN IF EXISTS valid_from;
        """
    )
