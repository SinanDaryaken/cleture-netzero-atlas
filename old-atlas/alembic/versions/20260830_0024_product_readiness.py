"""Add reviewed product-input catalogs and persistent regression history.

Revision ID: 20260830_0024
Revises: 20260829_0023
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_0024"
down_revision: str | None = "20260829_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FACILITIES = (
    ("FAC-001", "Aliağa Production Plant", "TR", "İzmir"),
    ("FAC-002", "Duisburg Steel Works", "DE", "North Rhine-Westphalia"),
    ("FAC-003", "Lyon Distribution Hub", "FR", "Auvergne-Rhône-Alpes"),
    ("FAC-004", "Houston Refining Campus", "US", "Texas"),
    ("FAC-005", "Toronto Assembly Plant", "CA", "Ontario"),
    ("FAC-006", "Manchester Textile Mill", "GB", "North West England"),
    ("FAC-007", "São Paulo Food Processing", "BR", "São Paulo"),
    ("FAC-008", "Monterrey Components Plant", "MX", "Nuevo León"),
    ("FAC-009", "Johannesburg Mining Services", "ZA", "Gauteng"),
    ("FAC-010", "Alexandria Fertilizer Terminal", "EG", "Alexandria"),
    ("FAC-011", "Dubai Logistics Free Zone", "AE", "Dubai"),
    ("FAC-012", "Jubail Petrochemical Complex", "SA", "Eastern Province"),
    ("FAC-013", "Pune Engineering Works", "IN", "Maharashtra"),
    ("FAC-014", "Shanghai Electronics Campus", "CN", "Shanghai"),
    ("FAC-015", "Nagoya Mobility Plant", "JP", "Aichi"),
    ("FAC-016", "Ulsan Battery Materials", "KR", "Ulsan"),
    ("FAC-017", "Melbourne Packaging Works", "AU", "Victoria"),
    ("FAC-018", "Singapore Data Operations", "SG", "Singapore"),
    ("FAC-019", "Rotterdam Circular Hub", "NL", "South Holland"),
    ("FAC-020", "Gothenburg Marine Works", "SE", "Västra Götaland"),
)

REGRESSION_CASE_NAMES = (
    "Identity energy conversion",
    "kWh to GJ conversion",
    "litre to cubic-metre conversion",
    "Calorific value is explicit",
    "No implicit conversion parameter",
    "Missing parameter has no result",
    "Incompatible currency conversion",
    "Multilingual concept identity",
    "Exact geography precedes global",
    "Global fallback is explicit",
    "LCA is rejected by CBAM",
    "CBAM is rejected by LCA",
    "Equivalent energy units agree",
    "Wheat PCF fallback trace",
    "Türkiye electricity isolation",
    "CBAM electricity isolation",
    "Passenger distance parameter",
    "Scope 1 diesel provenance",
)


def upgrade() -> None:
    op.create_table(
        "atlas_facilities",
        sa.Column("code", sa.String(128), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "country_code", sa.String(2), sa.ForeignKey("atlas_countries.code"), nullable=False
        ),
        sa.Column("region", sa.String(128)),
        sa.Column("electricity_connection_level", sa.String(32)),
        sa.Column(
            "industry_codes", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("registry_version", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "electricity_connection_level IS NULL OR "
            "electricity_connection_level IN ('distribution', 'transmission')",
            name="ck_atlas_facility_connection_level",
        ),
    )
    for column in ("country_code", "region", "registry_version", "active"):
        op.create_index(f"ix_atlas_facilities_{column}", "atlas_facilities", [column])

    op.create_table(
        "atlas_conversion_parameters",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("value", sa.Numeric(24, 12), nullable=False),
        sa.Column("unit", sa.String(128), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("country_code", sa.String(2), sa.ForeignKey("atlas_countries.code")),
        sa.Column(
            "facility_code",
            sa.String(128),
            sa.ForeignKey("atlas_facilities.code", ondelete="CASCADE"),
        ),
        sa.Column("valid_from", sa.Date()),
        sa.Column("valid_to", sa.Date()),
        sa.Column("provenance", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("review_status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("reviewed_by", sa.String(255)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_note", sa.Text()),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("value > 0", name="ck_atlas_conversion_parameter_positive"),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_atlas_conversion_parameter_validity",
        ),
        sa.CheckConstraint(
            "review_status IN ('draft', 'approved', 'rejected', 'superseded')",
            name="ck_atlas_conversion_parameter_review",
        ),
    )
    for column in (
        "name",
        "country_code",
        "facility_code",
        "valid_from",
        "valid_to",
        "review_status",
        "version",
        "active",
    ):
        op.create_index(
            f"ix_atlas_conversion_parameters_{column}", "atlas_conversion_parameters", [column]
        )

    op.create_table(
        "atlas_regression_cases",
        sa.Column("code", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("suite_version", sa.String(64), nullable=False),
        sa.Column("expected", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_atlas_regression_cases_suite_version", "atlas_regression_cases", ["suite_version"]
    )
    op.create_index("ix_atlas_regression_cases_active", "atlas_regression_cases", ["active"])

    op.create_table(
        "atlas_regression_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("suite_version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("changed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requested_by", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_atlas_regression_runs_suite_version", "atlas_regression_runs", ["suite_version"]
    )
    op.create_index("ix_atlas_regression_runs_status", "atlas_regression_runs", ["status"])

    op.create_table(
        "atlas_regression_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("atlas_regression_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_code", sa.String(64), sa.ForeignKey("atlas_regression_cases.code"), nullable=False
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("actual", sa.Text(), nullable=False),
        sa.Column("expected", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("run_id", "case_code", name="uq_atlas_regression_run_case"),
    )
    for column in ("run_id", "case_code", "status"):
        op.create_index(
            f"ix_atlas_regression_results_{column}", "atlas_regression_results", [column]
        )

    op.create_table(
        "atlas_regression_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("atlas_regression_runs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reviewed_by", sa.String(255), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "decision IN ('approved', 'rejected')", name="ck_atlas_regression_review_decision"
        ),
    )
    op.create_index(
        "ix_atlas_regression_reviews_decision", "atlas_regression_reviews", ["decision"]
    )

    facilities = sa.table(
        "atlas_facilities",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("country_code", sa.String()),
        sa.column("region", sa.String()),
        sa.column("industry_codes", sa.JSON()),
        sa.column("metadata_json", sa.JSON()),
        sa.column("registry_version", sa.String()),
        sa.column("active", sa.Boolean()),
    )
    op.bulk_insert(
        facilities,
        [
            {
                "code": code,
                "name": name,
                "country_code": country,
                "region": region,
                "industry_codes": {},
                "metadata_json": {"seed": "explorer-v1"},
                "registry_version": "2026.08.30",
                "active": True,
            }
            for code, name, country, region in FACILITIES
        ],
    )
    cases = sa.table(
        "atlas_regression_cases",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("suite_version", sa.String()),
        sa.column("expected", sa.JSON()),
        sa.column("metadata_json", sa.JSON()),
        sa.column("active", sa.Boolean()),
    )
    op.bulk_insert(
        cases,
        [
            {
                "code": f"TC-{index:06d}",
                "name": name,
                "suite_version": "2026.08.30",
                "expected": {},
                "metadata_json": {},
                "active": True,
            }
            for index, name in enumerate(REGRESSION_CASE_NAMES, start=1)
        ],
    )


def downgrade() -> None:
    op.drop_table("atlas_regression_reviews")
    op.drop_table("atlas_regression_results")
    op.drop_table("atlas_regression_runs")
    op.drop_table("atlas_regression_cases")
    op.drop_table("atlas_conversion_parameters")
    op.drop_table("atlas_facilities")
