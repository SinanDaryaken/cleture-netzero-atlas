from __future__ import annotations

import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import ClassVar

from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict

from atlas.domain.models import ParsedRecord
from atlas.ingestion.errors import PermanentIngestionError


class ConcitoRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    activity_id: str
    product: str
    country_code: str
    category: str
    lifecycle_stage: str
    factor_tco2e_per_t: Decimal
    source_member: str
    source_row: int

    def as_parsed_record(self) -> ParsedRecord:
        return ParsedRecord(
            data=self.model_dump(mode="json"),
            source_row=self.source_row,
            source_sheet=self.source_member,
            source_table=self.lifecycle_stage,
        )


class ConcitoParser:
    detail_labels: ClassVar[dict[str, str]] = {
        "Total (t CO2e/t)": "Total",
        "Agriculture (t CO2e/t)": "Agriculture",
        "ILUC (t CO2e/t)": "ILUC",
        "Other (t CO2e/t)": "Processing",
        "Packaging (t CO2e/t)": "Packaging",
        "Transport (t CO2e/t)": "Transport",
        "Retail (t CO2e/t)": "Retail",
    }
    countries: ClassVar[set[str]] = {"DK", "ES", "FR", "GB", "NL"}

    def __init__(
        self,
        *,
        expected_activities: int = 2700,
        expected_country_counts: dict[str, int] | None = None,
    ) -> None:
        self.metrics: dict[str, int] = {}
        self.expected_activities = expected_activities
        self.expected_country_counts = expected_country_counts or {
            country: 540 for country in self.countries
        }

    def parse(self, path: Path) -> tuple[ConcitoRow, ...]:
        with zipfile.ZipFile(path) as bundle:
            names = set(bundle.namelist())
            if "index.html" not in names:
                raise PermanentIngestionError("CONCITO bundle has no index.html")
            activities = self._index_activities(bundle.read("index.html"))
            rows: list[ConcitoRow] = []
            for source_row, activity in enumerate(activities, start=1):
                activity_id, product, country, category = activity
                member = f"activities/{activity_id}.html"
                if member not in names:
                    raise PermanentIngestionError(
                        f"CONCITO bundle has no detail page for {activity_id}"
                    )
                details = self._detail(bundle.read(member), activity_id)
                if details["Product Name"] != product:
                    raise PermanentIngestionError(
                        f"CONCITO product mismatch for {activity_id}"
                    )
                if details["Country"] != country or details["Category"] != category:
                    raise PermanentIngestionError(
                        f"CONCITO geography/category mismatch for {activity_id}"
                    )
                for label, stage in self.detail_labels.items():
                    rows.append(
                        ConcitoRow(
                            activity_id=activity_id,
                            product=product,
                            country_code=country,
                            category=category,
                            lifecycle_stage=stage,
                            factor_tco2e_per_t=self._decimal(
                                details[label], activity_id, label
                            ),
                            source_member=member,
                            source_row=source_row,
                        )
                    )
        expected_rows = self.expected_activities * len(self.detail_labels)
        if len(activities) != self.expected_activities or len(rows) != expected_rows:
            raise PermanentIngestionError(
                f"CONCITO expected {self.expected_activities:,} activities / "
                f"{expected_rows:,} results; "
                f"found {len(activities):,} / {len(rows):,}"
            )
        country_counts = {country: 0 for country in self.countries}
        for activity in activities:
            country_counts[activity[2]] += 1
        if country_counts != self.expected_country_counts:
            raise PermanentIngestionError(
                f"CONCITO v1.2 country coverage changed: {country_counts}"
            )
        self.metrics = {
            "input_activities": len(activities),
            "parsed_rows": len(rows),
            "zero_component_rows": sum(
                row.lifecycle_stage != "Total" and row.factor_tco2e_per_t == 0
                for row in rows
            ),
            "negative_lca_results": sum(row.factor_tco2e_per_t < 0 for row in rows),
            **{f"country_{code}_activities": count for code, count in country_counts.items()},
        }
        return tuple(rows)

    @classmethod
    def _index_activities(cls, content: bytes) -> list[tuple[str, str, str, str]]:
        soup = BeautifulSoup(content, "html.parser")
        headers = [cls._text(cell.get_text(" ", strip=True)) for cell in soup.select("thead th")]
        expected = {
            "Product Name (t CO2e/t)",
            "Country",
            "Category",
            "Total",
            "Agriculture",
            "ILUC",
            "Processing",
            "Packaging",
            "Transport",
            "Retail",
            "Id",
        }
        missing = expected - set(headers)
        if missing:
            raise PermanentIngestionError(
                "CONCITO index schema changed; missing headers: "
                + ", ".join(sorted(missing))
            )
        activities: list[tuple[str, str, str, str]] = []
        for row in soup.select("tbody tr"):
            cells = [cls._text(cell.get_text(" ", strip=True)) for cell in row.select("td")]
            record = dict(zip(headers, cells, strict=False))
            activity_id = record.get("Id")
            product = record.get("Product Name (t CO2e/t)")
            country = record.get("Country")
            category = record.get("Category")
            if not activity_id or not product or country not in cls.countries or not category:
                raise PermanentIngestionError("CONCITO index contains an incomplete activity")
            activities.append((activity_id, product, country, category))
        if len({activity[0] for activity in activities}) != len(activities):
            raise PermanentIngestionError("CONCITO index contains duplicate activity IDs")
        return activities

    @classmethod
    def _detail(cls, content: bytes, activity_id: str) -> dict[str, str]:
        soup = BeautifulSoup(content, "html.parser")
        details: dict[str, str] = {}
        for row in soup.select("tbody tr"):
            header = row.select_one("th")
            value = row.select_one("td")
            if header is not None and value is not None:
                details[cls._text(header.get_text(" ", strip=True))] = cls._text(
                    value.get_text(" ", strip=True)
                )
        expected = {"Product Name", "Country", "Category", "ID", *cls.detail_labels}
        missing = expected - set(details)
        if missing:
            raise PermanentIngestionError(
                f"CONCITO detail schema changed for {activity_id}; missing: "
                + ", ".join(sorted(missing))
            )
        if details["ID"] != activity_id:
            raise PermanentIngestionError(f"CONCITO detail ID mismatch for {activity_id}")
        return details

    @staticmethod
    def _text(value: object) -> str:
        return " ".join(str(value).split())

    @staticmethod
    def _decimal(value: str, activity_id: str, label: str) -> Decimal:
        try:
            result = Decimal(value)
        except InvalidOperation as error:
            raise PermanentIngestionError(
                f"CONCITO {activity_id} has invalid {label}: {value}"
            ) from error
        if not result.is_finite():
            raise PermanentIngestionError(
                f"CONCITO {activity_id} has non-finite {label}"
            )
        return result
