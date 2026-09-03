"""Add exhaustive unit-expression mapping inventory.

Revision ID: 20260828_0014
Revises: 20260828_0013
Create Date: 2026-08-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260828_0014"
down_revision: str | None = "20260828_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE atlas_unit_expression_mappings (
          id UUID PRIMARY KEY,
          layer VARCHAR(32) NOT NULL,
          raw_unit_hash VARCHAR(64) NOT NULL,
          raw_unit TEXT NOT NULL,
          normalized_expression TEXT NOT NULL,
          mapping_status VARCHAR(32) NOT NULL,
          canonical_expression TEXT,
          numerator_code VARCHAR(128),
          denominator_code VARCHAR(128),
          denominator_quantity NUMERIC(38, 18),
          reason_code VARCHAR(128) NOT NULL,
          registry_version VARCHAR(64) NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT uq_atlas_unit_expression_layer_hash UNIQUE (layer, raw_unit_hash)
        );
        CREATE INDEX ix_atlas_unit_expression_mappings_layer
          ON atlas_unit_expression_mappings (layer);
        CREATE INDEX ix_atlas_unit_expression_mappings_mapping_status
          ON atlas_unit_expression_mappings (mapping_status);
        CREATE INDEX ix_atlas_unit_expression_mappings_numerator_code
          ON atlas_unit_expression_mappings (numerator_code);
        CREATE INDEX ix_atlas_unit_expression_mappings_denominator_code
          ON atlas_unit_expression_mappings (denominator_code);
        CREATE INDEX ix_atlas_unit_expression_mappings_reason_code
          ON atlas_unit_expression_mappings (reason_code);
        CREATE INDEX ix_atlas_unit_expression_mappings_registry_version
          ON atlas_unit_expression_mappings (registry_version);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS atlas_unit_expression_mappings")
