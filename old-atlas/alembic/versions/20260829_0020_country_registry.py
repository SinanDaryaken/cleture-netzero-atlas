"""Add the central ISO country and multilingual label registry.

Revision ID: 20260829_0020
Revises: 20260829_0019
Create Date: 2026-08-29
"""

from __future__ import annotations

import gettext
import re
import unicodedata
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import pycountry
import sqlalchemy as sa

from alembic import op

revision: str = "20260829_0020"
down_revision: str | None = "20260829_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REGISTRY_VERSION = f"iso3166-pycountry-{pycountry.__version__}"
LOCALES = {
    "ar": "ar",
    "de": "de",
    "es": "es",
    "fa": "fa",
    "fr": "fr",
    "it": "it",
    "ja": "ja",
    "pt": "pt",
    "ru": "ru",
    "tr": "tr",
    "zh": "zh_CN",
}
VERIFIED_ALIASES = {
    "GB": (("en", "UK"), ("en", "Great Britain"), ("tr", "İngiltere")),
    "NL": (("en", "Holland"), ("tr", "Hollanda")),
    "TR": (("en", "Turkey"), ("en", "Turkiye"), ("tr", "Türkiye")),
    "US": (("en", "USA"), ("en", "United States of America"), ("tr", "Amerika")),
}


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^\w]+", " ", without_marks).split())


def _label(
    *,
    country_code: str,
    language: str,
    value: str,
    label_type: str,
    source: str,
    created_at: datetime,
) -> dict[str, object]:
    return {
        "id": uuid4(),
        "country_code": country_code,
        "language": language,
        "label": value,
        "normalized_label": _normalize(value),
        "label_type": label_type,
        "source": source,
        "review_status": "approved",
        "created_at": created_at,
    }


def upgrade() -> None:
    countries = op.create_table(
        "atlas_countries",
        sa.Column("code", sa.String(length=2), primary_key=True),
        sa.Column("alpha3", sa.String(length=3), nullable=False),
        sa.Column("numeric_code", sa.String(length=3), nullable=True),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("registry_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("alpha3", name="uq_atlas_countries_alpha3"),
        sa.UniqueConstraint("numeric_code", name="uq_atlas_countries_numeric_code"),
    )
    labels = op.create_table(
        "atlas_country_labels",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "country_code",
            sa.String(length=2),
            sa.ForeignKey("atlas_countries.code", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("normalized_label", sa.String(length=255), nullable=False),
        sa.Column("label_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "country_code",
            "language",
            "normalized_label",
            name="uq_atlas_country_label",
        ),
    )
    op.create_index("ix_atlas_countries_alpha3", "atlas_countries", ["alpha3"])
    op.create_index("ix_atlas_countries_active", "atlas_countries", ["active"])
    op.create_index("ix_atlas_countries_registry_version", "atlas_countries", ["registry_version"])
    op.create_index(
        "ix_atlas_country_labels_country_code", "atlas_country_labels", ["country_code"]
    )
    op.create_index("ix_atlas_country_labels_language", "atlas_country_labels", ["language"])
    op.create_index(
        "ix_atlas_country_labels_normalized_label",
        "atlas_country_labels",
        ["normalized_label"],
    )
    op.create_index("ix_atlas_country_labels_label_type", "atlas_country_labels", ["label_type"])
    op.create_index(
        "ix_atlas_country_labels_review_status", "atlas_country_labels", ["review_status"]
    )

    now = datetime.now(UTC)
    country_rows: list[dict[str, object]] = []
    label_rows: list[dict[str, object]] = []
    seen_labels: set[tuple[str, str, str]] = set()
    translators = {
        language: gettext.translation(
            "iso3166-1",
            pycountry.LOCALES_DIR,
            languages=[locale],
            fallback=True,
        )
        for language, locale in LOCALES.items()
    }

    def add_label(code: str, language: str, value: str, label_type: str, source: str) -> None:
        normalized = _normalize(value)
        key = (code, language, normalized)
        if not normalized or key in seen_labels:
            return
        seen_labels.add(key)
        label_rows.append(
            _label(
                country_code=code,
                language=language,
                value=value,
                label_type=label_type,
                source=source,
                created_at=now,
            )
        )

    for country in sorted(pycountry.countries, key=lambda item: item.alpha_2):
        country_rows.append(
            {
                "code": country.alpha_2,
                "alpha3": country.alpha_3,
                "numeric_code": getattr(country, "numeric", None),
                "canonical_name": country.name,
                "active": True,
                "registry_version": REGISTRY_VERSION,
                "created_at": now,
                "updated_at": now,
            }
        )
        add_label(country.alpha_2, "und", country.alpha_2, "code", REGISTRY_VERSION)
        add_label(country.alpha_2, "und", country.alpha_3, "code", REGISTRY_VERSION)
        add_label(country.alpha_2, "en", country.name, "canonical", REGISTRY_VERSION)
        for attribute, label_type in (("official_name", "official"), ("common_name", "common")):
            value = getattr(country, attribute, None)
            if value:
                add_label(country.alpha_2, "en", value, label_type, REGISTRY_VERSION)
        for language, translator in translators.items():
            translated = translator.gettext(country.name)
            add_label(country.alpha_2, language, translated, "common", REGISTRY_VERSION)
        for language, alias in VERIFIED_ALIASES.get(country.alpha_2, ()):
            add_label(
                country.alpha_2,
                language,
                alias,
                "alias",
                "atlas-verified-country-aliases-v1",
            )

    op.bulk_insert(countries, country_rows)
    op.bulk_insert(labels, label_rows)


def downgrade() -> None:
    op.drop_table("atlas_country_labels")
    op.drop_table("atlas_countries")
