"""Allow a reviewed term and a new draft to coexist.

Revision ID: 20260829_0018
Revises: 20260829_0017
Create Date: 2026-08-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260829_0018"
down_revision: str | None = "20260829_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE atlas_concept_labels
          DROP CONSTRAINT uq_atlas_concept_label;
        ALTER TABLE atlas_concept_labels
          ADD CONSTRAINT uq_atlas_concept_label
          UNIQUE (concept_id, language, normalized_label, review_status);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM atlas_concept_labels newer
         USING atlas_concept_labels older
         WHERE newer.concept_id = older.concept_id
           AND newer.language = older.language
           AND newer.normalized_label = older.normalized_label
           AND newer.id > older.id;
        ALTER TABLE atlas_concept_labels
          DROP CONSTRAINT uq_atlas_concept_label;
        ALTER TABLE atlas_concept_labels
          ADD CONSTRAINT uq_atlas_concept_label
          UNIQUE (concept_id, language, normalized_label);
        """
    )
