from __future__ import annotations

import json
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from atlas.domain.models import ParsedRecord
from atlas.ingestion.errors import PermanentIngestionError


class EmberRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity: str = Field(min_length=1)
    entity_code: str | None = None
    is_aggregate_entity: bool | None = None
    reference_year: int = Field(ge=1900, le=2200)
    intensity_gco2e_per_kwh: Decimal | None = None
    source_row: int = Field(ge=1)

    def as_parsed_record(self) -> ParsedRecord:
        return ParsedRecord(
            data=self.model_dump(mode="json"),
            source_row=self.source_row,
            source_table="data",
        )


class EmberParser:
    def __init__(self) -> None:
        self.metrics: dict[str, int] = {}

    def parse(self, content: bytes) -> tuple[EmberRow, ...]:
        try:
            payload = json.loads(content, parse_float=Decimal)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PermanentIngestionError("Ember response is not valid JSON") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise PermanentIngestionError("Ember response contract changed")

        rows: list[EmberRow] = []
        for source_row, item in enumerate(payload["data"], start=1):
            if not isinstance(item, dict) or set(item) != {
                "entity",
                "entity_code",
                "is_aggregate_entity",
                "date",
                "emissions_intensity_gco2_per_kwh",
            }:
                raise PermanentIngestionError(
                    f"Ember carbon-intensity schema changed at record {source_row}"
                )
            try:
                rows.append(
                    EmberRow(
                        entity=item["entity"],
                        entity_code=item["entity_code"],
                        is_aggregate_entity=item["is_aggregate_entity"],
                        reference_year=int(item["date"]),
                        intensity_gco2e_per_kwh=item["emissions_intensity_gco2_per_kwh"],
                        source_row=source_row,
                    )
                )
            except (TypeError, ValueError) as error:
                raise PermanentIngestionError(
                    f"Ember carbon-intensity record is invalid at {source_row}"
                ) from error
        if not rows:
            raise PermanentIngestionError("Ember response contains no records")
        self.metrics = {
            "parsed_rows": len(rows),
            "null_values": sum(row.intensity_gco2e_per_kwh is None for row in rows),
            "negative_values": sum(
                row.intensity_gco2e_per_kwh is not None and row.intensity_gco2e_per_kwh < 0
                for row in rows
            ),
            "minimum_reference_year": min(row.reference_year for row in rows),
            "maximum_reference_year": max(row.reference_year for row in rows),
        }
        return tuple(rows)
