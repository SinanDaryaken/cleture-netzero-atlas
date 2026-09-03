"""Use the Simplified Chinese ISO translation catalog.

Revision ID: 20260829_0021
Revises: 20260829_0020
Create Date: 2026-08-29
"""

from __future__ import annotations

import gettext
import re
import unicodedata
from collections.abc import Sequence

import pycountry
import sqlalchemy as sa

from alembic import op

revision: str = "20260829_0021"
down_revision: str | None = "20260829_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^\w]+", " ", without_marks).split())


def upgrade() -> None:
    translator = gettext.translation(
        "iso3166-1",
        pycountry.LOCALES_DIR,
        languages=["zh_CN"],
        fallback=True,
    )
    connection = op.get_bind()
    statement = sa.text(
        """
        UPDATE atlas_country_labels
           SET label = :label,
               normalized_label = :normalized_label
         WHERE country_code = :country_code
           AND language = 'zh'
           AND label_type = 'common'
           AND source LIKE 'iso3166-pycountry-%'
        """
    )
    connection.execute(
        statement,
        [
            {
                "country_code": country.alpha_2,
                "label": translated,
                "normalized_label": _normalize(translated),
            }
            for country in pycountry.countries
            if (translated := translator.gettext(country.name))
        ],
    )


def downgrade() -> None:
    # Translation corrections are not reversed; the ISO identity rows are unchanged.
    pass
