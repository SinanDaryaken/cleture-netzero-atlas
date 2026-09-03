# ruff: noqa: E501
"""Add the recommendation serving projection.

Revision ID: 20260829_0016
Revises: 20260828_0015
Create Date: 2026-08-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260829_0016"
down_revision: str | None = "20260828_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE atlas_factor_applicabilities (
            factor_version_id UUID PRIMARY KEY REFERENCES atlas_factor_versions(id) ON DELETE CASCADE,
            concept_code VARCHAR(255),
            family_code VARCHAR(64) NOT NULL,
            calculation_role VARCHAR(64) NOT NULL,
            calculation_method VARCHAR(64) NOT NULL,
            scope_category VARCHAR(32),
            activity_basis VARCHAR(64) NOT NULL,
            boundary VARCHAR(128),
            fallback_class VARCHAR(32) NOT NULL,
            qualifiers JSONB NOT NULL DEFAULT '{}'::jsonb,
            policy_version VARCHAR(64) NOT NULL,
            review_status VARCHAR(32) NOT NULL DEFAULT 'projected',
            reviewed_by VARCHAR(255),
            reviewed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_atlas_factor_applicabilities_concept ON atlas_factor_applicabilities(concept_code);
        CREATE INDEX ix_atlas_factor_applicabilities_family ON atlas_factor_applicabilities(family_code);
        CREATE INDEX ix_atlas_factor_applicabilities_role ON atlas_factor_applicabilities(calculation_role);
        CREATE INDEX ix_atlas_factor_applicabilities_scope ON atlas_factor_applicabilities(scope_category);
        CREATE INDEX ix_atlas_factor_applicabilities_basis ON atlas_factor_applicabilities(activity_basis);
        CREATE INDEX ix_atlas_factor_applicabilities_boundary ON atlas_factor_applicabilities(boundary);
        CREATE INDEX ix_atlas_factor_applicabilities_fallback ON atlas_factor_applicabilities(fallback_class);
        CREATE INDEX ix_atlas_factor_applicabilities_policy ON atlas_factor_applicabilities(policy_version);
        CREATE INDEX ix_atlas_factor_applicabilities_review ON atlas_factor_applicabilities(review_status);

        CREATE TABLE atlas_factor_relationships (
            id UUID PRIMARY KEY,
            from_factor_id UUID NOT NULL REFERENCES atlas_factors(id) ON DELETE CASCADE,
            to_factor_id UUID NOT NULL REFERENCES atlas_factors(id) ON DELETE CASCADE,
            relationship_type VARCHAR(32) NOT NULL,
            evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
            policy_version VARCHAR(64) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_atlas_factor_relationship UNIQUE
                (from_factor_id, to_factor_id, relationship_type)
        );
        CREATE INDEX ix_atlas_factor_relationships_from ON atlas_factor_relationships(from_factor_id);
        CREATE INDEX ix_atlas_factor_relationships_to ON atlas_factor_relationships(to_factor_id);
        CREATE INDEX ix_atlas_factor_relationships_type ON atlas_factor_relationships(relationship_type);
        CREATE INDEX ix_atlas_factor_relationships_policy ON atlas_factor_relationships(policy_version);

        CREATE TABLE atlas_fallback_policies (
            id UUID PRIMARY KEY,
            country_code VARCHAR(2) NOT NULL DEFAULT '*',
            calculation_profile VARCHAR(128) NOT NULL,
            family_code VARCHAR(64) NOT NULL,
            tier_code VARCHAR(32) NOT NULL,
            tier_rank INTEGER NOT NULL,
            proxy BOOLEAN NOT NULL DEFAULT false,
            requires_acceptance BOOLEAN NOT NULL DEFAULT false,
            policy_version VARCHAR(64) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_atlas_fallback_policy_tier UNIQUE
                (calculation_profile, country_code, family_code, tier_code)
        );
        CREATE INDEX ix_atlas_fallback_policies_country ON atlas_fallback_policies(country_code);
        CREATE INDEX ix_atlas_fallback_policies_profile ON atlas_fallback_policies(calculation_profile);
        CREATE INDEX ix_atlas_fallback_policies_family ON atlas_fallback_policies(family_code);
        CREATE INDEX ix_atlas_fallback_policies_policy ON atlas_fallback_policies(policy_version);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS atlas_fallback_policies;
        DROP TABLE IF EXISTS atlas_factor_relationships;
        DROP TABLE IF EXISTS atlas_factor_applicabilities;
        """
    )
