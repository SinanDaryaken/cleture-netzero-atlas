"""Add source-backed semantic geography roles.

Revision ID: 20260829_0019
Revises: 20260829_0018
Create Date: 2026-08-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260829_0019"
down_revision: str | None = "20260829_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE atlas_factor_versions
          ADD COLUMN geography_roles JSONB NOT NULL DEFAULT '[]'::jsonb;

        CREATE INDEX ix_atlas_factor_versions_geography_roles
          ON atlas_factor_versions USING gin (geography_roles);

        UPDATE atlas_factor_versions AS fv
           SET geography_roles = COALESCE(
               (
                 SELECT jsonb_agg(
                   jsonb_build_object(
                     'role', 'market',
                     'geography', geography,
                     'derivation', 'source_declared',
                     'source_field', 'Country',
                     'rule_version', 'concito-geography-v1',
                     'confidence', 1.0
                   )
                 )
                 FROM jsonb_array_elements(fv.applicable_geographies) AS geography
               ),
               '[]'::jsonb
           )
          FROM atlas_factors AS factor
          JOIN atlas_sources AS source ON source.id = factor.source_id
         WHERE factor.id = fv.factor_id
           AND source.code = 'CONCITO';

        UPDATE atlas_factor_versions AS fv
           SET geography_roles =
               CASE
                 WHEN fv.origin_geography IS NULL THEN '[]'::jsonb
                 ELSE jsonb_build_array(
                   jsonb_build_object(
                     'role', 'production_origin',
                     'geography', fv.origin_geography,
                     'derivation', 'source_declared',
                     'source_field', 'origin_region',
                     'rule_version', 'wrap-geography-v1',
                     'confidence', 1.0
                   )
                 )
               END
               || COALESCE(
                 (
                   SELECT jsonb_agg(
                     jsonb_build_object(
                       'role', 'calculation_applicability',
                       'geography', geography,
                       'derivation', 'source_declared',
                       'source_field', 'applicable_region',
                       'rule_version', 'wrap-geography-v1',
                       'confidence', 1.0
                     )
                   )
                   FROM jsonb_array_elements(fv.applicable_geographies) AS geography
                 ),
                 '[]'::jsonb
               )
          FROM atlas_factors AS factor
          JOIN atlas_sources AS source ON source.id = factor.source_id
         WHERE factor.id = fv.factor_id
           AND source.code = 'WRAP';

        ALTER TABLE atlas_factor_versions
          ALTER COLUMN geography_roles DROP DEFAULT;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS ix_atlas_factor_versions_geography_roles;
        ALTER TABLE atlas_factor_versions DROP COLUMN IF EXISTS geography_roles;
        """
    )
