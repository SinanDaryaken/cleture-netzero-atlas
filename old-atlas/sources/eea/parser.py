from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from atlas.domain.models import ParsedRecord
from atlas.ingestion.errors import PermanentIngestionError


class EeaRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    record_id: int = Field(ge=1)
    nfr: str
    sector: str
    table: str
    factor_type: str
    technology: str
    fuel: str
    abatement: str
    region: str
    pollutant: str
    value: Decimal | None
    source_value: str
    unit: str
    ci_lower: str
    ci_upper: str
    reference: str
    chapter_url: str
    category_code: str

    @property
    def is_canonical_ghg_factor(self) -> bool:
        return self.pollutant in {"CO2", "CO2 lube", "CH4", "N2O"} and self.value is not None

    def as_parsed_record(self) -> ParsedRecord:
        return ParsedRecord(
            data=self.model_dump(mode="json"),
            source_row=self.record_id,
            source_table=self.table,
        )


class EeaDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    edition: int
    index_name: str
    refreshed_at: str
    rows: tuple[EeaRow, ...]

    @property
    def parsed_records(self) -> tuple[ParsedRecord, ...]:
        return tuple(row.as_parsed_record() for row in self.rows)


class EeaParser:
    EXPECTED_FIELDS: ClassVar[set[str]] = {
        "ID",
        "NFR",
        "Sector",
        "Table",
        "Type",
        "Technology",
        "Fuel",
        "Abatement",
        "Region",
        "Pollutant",
        "Value",
        "Unit",
        "CI_lower",
        "CI_upper",
        "Reference",
        "Link",
        "code",
    }

    def __init__(self) -> None:
        self.metrics: dict[str, int] = {}

    def parse(self, content: bytes) -> EeaDocument:
        try:
            payload = json.loads(content, parse_float=Decimal)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PermanentIngestionError("EEA viewer snapshot is not valid JSON") from error
        if not isinstance(payload, dict) or set(payload) != {
            "edition",
            "index_name",
            "refreshed_at",
            "records",
        }:
            raise PermanentIngestionError("EEA viewer snapshot contract changed")
        if payload["edition"] != 2023 or not isinstance(payload["records"], list):
            raise PermanentIngestionError("EEA Guidebook edition or record list changed")

        rows: list[EeaRow] = []
        seen_ids: set[int] = set()
        for position, item in enumerate(payload["records"], start=1):
            if not isinstance(item, dict) or set(item) != self.EXPECTED_FIELDS:
                raise PermanentIngestionError(
                    f"EEA viewer schema changed at record position {position}"
                )
            try:
                record_id = int(item["ID"])
                if record_id in seen_ids:
                    raise PermanentIngestionError(f"EEA viewer duplicated record ID {record_id}")
                seen_ids.add(record_id)
                source_value = self._text(item["Value"])
                rows.append(
                    EeaRow(
                        record_id=record_id,
                        nfr=self._text(item["NFR"]),
                        sector=self._text(item["Sector"]),
                        table=self._text(item["Table"]),
                        factor_type=self._text(item["Type"]),
                        technology=self._text(item["Technology"]),
                        fuel=self._text(item["Fuel"]),
                        abatement=self._text(item["Abatement"]),
                        region=self._text(item["Region"]),
                        pollutant=self._text(item["Pollutant"]),
                        value=self._decimal(source_value),
                        source_value=source_value,
                        unit=self._text(item["Unit"]),
                        ci_lower=self._text(item["CI_lower"]),
                        ci_upper=self._text(item["CI_upper"]),
                        reference=self._text(item["Reference"]),
                        chapter_url=self._text(item["Link"]),
                        category_code=self._text(item["code"]),
                    )
                )
            except PermanentIngestionError:
                raise
            except (TypeError, ValueError) as error:
                raise PermanentIngestionError(
                    f"EEA viewer record is invalid at position {position}"
                ) from error
        if not rows:
            raise PermanentIngestionError("EEA viewer snapshot contains no records")
        if [row.record_id for row in rows] != sorted(seen_ids):
            raise PermanentIngestionError("EEA viewer records are not sorted by ID")

        numeric_rows = sum(row.value is not None for row in rows)
        canonical_rows = sum(row.is_canonical_ghg_factor for row in rows)
        self.metrics = {
            "parsed_rows": len(rows),
            "numeric_rows": numeric_rows,
            "non_numeric_rows": len(rows) - numeric_rows,
            "canonical_ghg_rows": canonical_rows,
            "source_observation_rows": numeric_rows - canonical_rows,
            "co2_rows": sum(
                row.value is not None and row.pollutant == "CO2" for row in rows
            ),
            "co2_lube_rows": sum(
                row.value is not None and row.pollutant == "CO2 lube" for row in rows
            ),
            "ch4_rows": sum(
                row.value is not None and row.pollutant == "CH4" for row in rows
            ),
            "n2o_rows": sum(
                row.value is not None and row.pollutant == "N2O" for row in rows
            ),
        }
        return EeaDocument(
            edition=payload["edition"],
            index_name=str(payload["index_name"]),
            refreshed_at=str(payload["refreshed_at"]),
            rows=tuple(rows),
        )

    @staticmethod
    def _text(value: Any) -> str:
        return "" if value is None else str(value).strip()

    @staticmethod
    def _decimal(value: str) -> Decimal | None:
        if not value:
            return None
        try:
            return Decimal(value)
        except InvalidOperation:
            return None
