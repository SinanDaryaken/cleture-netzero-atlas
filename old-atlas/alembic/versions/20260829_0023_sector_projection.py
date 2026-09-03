# ruff: noqa: E501, RUF001
"""Add the versioned business-sector projection and backfill all factor versions.

Revision ID: 20260829_0023
Revises: 20260829_0022
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from atlas.sectors import SECTOR_CATEGORIES, SECTOR_REGISTRY, SECTOR_REGISTRY_VERSION

revision: str = "20260829_0023"
down_revision: str | None = "20260829_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "atlas_sectors",
        sa.Column("code", sa.String(length=64), primary_key=True),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("registry_version", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_atlas_sectors_registry_version", "atlas_sectors", ["registry_version"])
    op.create_index("ix_atlas_sectors_active", "atlas_sectors", ["active"])

    op.create_table(
        "atlas_sector_labels",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "sector_code",
            sa.String(length=64),
            sa.ForeignKey("atlas_sectors.code", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("normalized_label", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="approved"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "sector_code", "language", "normalized_label", name="uq_atlas_sector_label"
        ),
    )
    op.create_index("ix_atlas_sector_labels_sector_code", "atlas_sector_labels", ["sector_code"])
    op.create_index("ix_atlas_sector_labels_language", "atlas_sector_labels", ["language"])
    op.create_index(
        "ix_atlas_sector_labels_normalized_label", "atlas_sector_labels", ["normalized_label"]
    )
    op.create_index(
        "ix_atlas_sector_labels_review_status", "atlas_sector_labels", ["review_status"]
    )

    op.create_table(
        "atlas_sector_categories",
        sa.Column("code", sa.String(length=64), primary_key=True),
        sa.Column(
            "sector_code",
            sa.String(length=64),
            sa.ForeignKey("atlas_sectors.code", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.Column("name_tr", sa.String(length=255), nullable=False),
        sa.Column("registry_version", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_atlas_sector_categories_sector_code", "atlas_sector_categories", ["sector_code"]
    )
    op.create_index(
        "ix_atlas_sector_categories_registry_version",
        "atlas_sector_categories",
        ["registry_version"],
    )
    op.create_index("ix_atlas_sector_categories_active", "atlas_sector_categories", ["active"])

    op.create_table(
        "atlas_factor_sector_assignments",
        sa.Column(
            "factor_version_id",
            sa.Uuid(),
            sa.ForeignKey("atlas_factor_versions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "sector_code", sa.String(length=64), sa.ForeignKey("atlas_sectors.code"), nullable=False
        ),
        sa.Column(
            "category_code",
            sa.String(length=64),
            sa.ForeignKey("atlas_sector_categories.code"),
            nullable=False,
        ),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "derivation", sa.String(length=64), nullable=False, server_default="verified_crosswalk"
        ),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("mapping_version", sa.String(length=64), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="approved"),
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
        "ix_atlas_factor_sector_assignments_sector_code",
        "atlas_factor_sector_assignments",
        ["sector_code"],
    )
    op.create_index(
        "ix_atlas_factor_sector_assignments_category_code",
        "atlas_factor_sector_assignments",
        ["category_code"],
    )
    op.create_index(
        "ix_atlas_factor_sector_assignments_mapping_version",
        "atlas_factor_sector_assignments",
        ["mapping_version"],
    )
    op.create_index(
        "ix_atlas_factor_sector_assignments_review_status",
        "atlas_factor_sector_assignments",
        ["review_status"],
    )

    sector_table = sa.table(
        "atlas_sectors",
        sa.column("code", sa.String()),
        sa.column("canonical_name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("registry_version", sa.String()),
        sa.column("active", sa.Boolean()),
    )
    op.bulk_insert(
        sector_table,
        [
            {
                "code": sector.code,
                "canonical_name": sector.name_en,
                "description": sector.description,
                "registry_version": SECTOR_REGISTRY_VERSION,
                "active": True,
            }
            for sector in SECTOR_REGISTRY
        ],
    )
    category_table = sa.table(
        "atlas_sector_categories",
        sa.column("code", sa.String()),
        sa.column("sector_code", sa.String()),
        sa.column("name_en", sa.String()),
        sa.column("name_tr", sa.String()),
        sa.column("registry_version", sa.String()),
        sa.column("active", sa.Boolean()),
    )
    op.bulk_insert(
        category_table,
        [
            {
                "code": category.code,
                "sector_code": category.sector_code,
                "name_en": category.name_en,
                "name_tr": category.name_tr,
                "registry_version": SECTOR_REGISTRY_VERSION,
                "active": True,
            }
            for category in SECTOR_CATEGORIES
        ],
    )
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO atlas_sector_labels
                (id, sector_code, language, label, normalized_label, source, review_status)
            SELECT gen_random_uuid(), code, language, label, lower(label), 'atlas-sector-registry', 'approved'
              FROM (
                    SELECT code, 'en' AS language, canonical_name AS label FROM atlas_sectors
                    UNION ALL
                    SELECT code, 'tr', CASE code
                        WHEN 'consumer_goods_services' THEN 'Tüketici Ürünleri ve Hizmetleri'
                        WHEN 'materials_manufacturing' THEN 'Malzemeler ve İmalat'
                        WHEN 'energy' THEN 'Enerji'
                        WHEN 'restaurants_accommodation' THEN 'Restoranlar ve Konaklama'
                        WHEN 'transport' THEN 'Ulaşım'
                        WHEN 'buildings_infrastructure' THEN 'Binalar ve Altyapı'
                        WHEN 'agriculture_forestry_fishing' THEN 'Tarım / Avcılık / Ormancılık / Balıkçılık'
                        WHEN 'land_use' THEN 'Arazi Kullanımı'
                        WHEN 'waste' THEN 'Atık'
                        WHEN 'water' THEN 'Su'
                        ELSE 'Sektörler Arası / Genel'
                    END FROM atlas_sectors
              ) labels
            """
        )
    )
    _backfill_assignments(connection)


def _backfill_assignments(connection: sa.Connection) -> None:
    connection.execute(
        sa.text(
            """
            WITH normalized AS (
                SELECT id,
                       taxonomy_code,
                       regexp_replace(lower(coalesce(taxonomy_code, 'atlas.unmapped')), '^atlas\\.', '') AS taxonomy,
                       regexp_replace(
                           regexp_replace(lower(coalesce(taxonomy_code, '')), '^.*spend\\.economic_sector\\.', ''),
                           '[^0-9]', '', 'g'
                       ) AS spend_code
                  FROM atlas_factor_versions
            ), classified AS (
                SELECT id, taxonomy_code,
                    CASE
                        WHEN taxonomy LIKE 'spend.economic_sector.%' AND spend_code LIKE '11%' THEN 'agriculture_forestry_fishing'
                        WHEN taxonomy LIKE 'spend.economic_sector.%' AND spend_code LIKE ANY (ARRAY['21%', '31%', '32%', '33%']) THEN 'materials_manufacturing'
                        WHEN taxonomy LIKE 'spend.economic_sector.%' AND spend_code LIKE '2213%' THEN 'water'
                        WHEN taxonomy LIKE 'spend.economic_sector.%' AND spend_code LIKE '22%' THEN 'energy'
                        WHEN taxonomy LIKE 'spend.economic_sector.%' AND (spend_code LIKE '23%' OR spend_code LIKE '531%') THEN 'buildings_infrastructure'
                        WHEN taxonomy LIKE 'spend.economic_sector.%' AND spend_code LIKE ANY (ARRAY['48%', '49%']) THEN 'transport'
                        WHEN taxonomy LIKE 'spend.economic_sector.%' AND spend_code LIKE ANY (ARRAY['721%', '722%']) THEN 'restaurants_accommodation'
                        WHEN taxonomy LIKE 'spend.economic_sector.%' AND spend_code LIKE '562%' THEN 'waste'
                        WHEN taxonomy LIKE 'spend.economic_sector.%' THEN 'consumer_goods_services'
                        WHEN taxonomy LIKE 'construction_product%' THEN 'buildings_infrastructure'
                        WHEN taxonomy LIKE 'food%' OR taxonomy LIKE 'services%' THEN 'consumer_goods_services'
                        WHEN taxonomy LIKE 'energy%' THEN 'energy'
                        WHEN taxonomy LIKE 'material%' OR taxonomy LIKE 'industrial_processes%' THEN 'materials_manufacturing'
                        WHEN taxonomy LIKE 'transport%' OR taxonomy LIKE 'emep_eea.nfr.1_a_3%' THEN 'transport'
                        WHEN taxonomy LIKE 'agriculture%' OR taxonomy LIKE 'emep_eea.nfr.1_a_4_c%' THEN 'agriculture_forestry_fishing'
                        WHEN taxonomy LIKE 'emep_eea.nfr.1_a_2%' THEN 'materials_manufacturing'
                        WHEN taxonomy LIKE 'emep_eea.nfr.1_a_4_a%' OR taxonomy LIKE 'emep_eea.nfr.1_a_4_b%' THEN 'buildings_infrastructure'
                        WHEN taxonomy LIKE 'waste%' THEN 'waste'
                        WHEN taxonomy LIKE 'land_use%' THEN 'land_use'
                        WHEN taxonomy LIKE 'water%' THEN 'water'
                        ELSE 'cross_sector'
                    END AS sector_code,
                    CASE
                        WHEN taxonomy LIKE 'spend.economic_sector.%' AND spend_code LIKE '11%' THEN 'agriculture'
                        WHEN taxonomy LIKE 'spend.economic_sector.%' AND spend_code LIKE '21%' THEN 'mining'
                        WHEN taxonomy LIKE 'spend.economic_sector.%' AND spend_code LIKE ANY (ARRAY['31%', '32%', '33%']) THEN 'manufacturing'
                        WHEN taxonomy LIKE 'spend.economic_sector.%' AND spend_code LIKE '2213%' THEN 'water_supply_treatment'
                        WHEN taxonomy LIKE 'spend.economic_sector.%' AND spend_code LIKE '22%' THEN 'energy_utilities'
                        WHEN taxonomy LIKE 'spend.economic_sector.%' AND spend_code LIKE '23%' THEN 'construction'
                        WHEN taxonomy LIKE 'spend.economic_sector.%' AND spend_code LIKE '531%' THEN 'buildings_real_estate'
                        WHEN taxonomy LIKE 'spend.economic_sector.%' AND spend_code LIKE ANY (ARRAY['48%', '49%']) THEN 'transport_services'
                        WHEN taxonomy LIKE 'spend.economic_sector.%' AND spend_code LIKE '721%' THEN 'accommodation'
                        WHEN taxonomy LIKE 'spend.economic_sector.%' AND spend_code LIKE '722%' THEN 'food_services'
                        WHEN taxonomy LIKE 'spend.economic_sector.%' AND spend_code LIKE '562%' THEN 'waste_treatment'
                        WHEN taxonomy LIKE 'spend.economic_sector.%' THEN 'other_consumer'
                        WHEN taxonomy LIKE 'construction_product%' THEN 'construction_products'
                        WHEN taxonomy LIKE 'food%' THEN 'food_beverages'
                        WHEN taxonomy LIKE 'services%' THEN 'services'
                        WHEN taxonomy LIKE 'energy%.electricity%' THEN 'electricity'
                        WHEN taxonomy LIKE 'energy%' AND (taxonomy LIKE '%heat%' OR taxonomy LIKE '%cooling%') THEN 'heat_cooling'
                        WHEN taxonomy LIKE 'energy%' THEN 'fuels'
                        WHEN taxonomy LIKE 'material%' THEN 'materials'
                        WHEN taxonomy LIKE 'industrial_processes%' THEN 'industrial_processes'
                        WHEN taxonomy LIKE 'transport%freight%' THEN 'freight_transport'
                        WHEN taxonomy LIKE 'transport%passenger%' THEN 'passenger_transport'
                        WHEN taxonomy LIKE 'transport%' OR taxonomy LIKE 'emep_eea.nfr.1_a_3%' THEN 'transport_services'
                        WHEN taxonomy LIKE 'agriculture%' OR taxonomy LIKE 'emep_eea.nfr.1_a_4_c%' THEN 'agriculture'
                        WHEN taxonomy LIKE 'emep_eea.nfr.1_a_2%' THEN 'manufacturing'
                        WHEN taxonomy LIKE 'emep_eea.nfr.1_a_4_a%' OR taxonomy LIKE 'emep_eea.nfr.1_a_4_b%' THEN 'buildings_real_estate'
                        WHEN taxonomy LIKE 'waste%' THEN 'waste_treatment'
                        WHEN taxonomy LIKE 'land_use%' THEN 'land_use'
                        WHEN taxonomy LIKE 'water%' THEN 'water_supply_treatment'
                        WHEN taxonomy LIKE 'refrigerants%' THEN 'refrigerants'
                        WHEN taxonomy LIKE 'methodology%' THEN 'methodology'
                        ELSE 'general'
                    END AS category_code,
                    CASE WHEN taxonomy LIKE ANY (ARRAY['unmapped%', 'source.%']) THEN 70 ELSE 100 END AS confidence
                FROM normalized
            )
            INSERT INTO atlas_factor_sector_assignments
                (factor_version_id, sector_code, category_code, is_primary, derivation,
                 confidence, evidence, mapping_version, review_status)
            SELECT id, sector_code, category_code, true, 'verified_crosswalk', confidence,
                   jsonb_build_object('taxonomy_code', taxonomy_code, 'rule', 'sector-registry-v1'),
                   :mapping_version, 'approved'
              FROM classified
            """
        ),
        {"mapping_version": SECTOR_REGISTRY_VERSION},
    )


def downgrade() -> None:
    op.drop_table("atlas_factor_sector_assignments")
    op.drop_table("atlas_sector_categories")
    op.drop_table("atlas_sector_labels")
    op.drop_table("atlas_sectors")
