from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from atlas.domain.models import ParsedRecord
from atlas.ingestion.errors import PermanentIngestionError


class OekobaudatRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    dataset_uuid: str
    dataset_record_version: str
    name_de: str | None = None
    name_en: str | None = None
    category_original: str | None = None
    category_en: str | None = None
    conformity: str
    background_databases: str | None = None
    geography_code: str
    dataset_type: str
    reference_year: int
    valid_until_year: int | None = None
    original_url: str
    declaration_owner: str | None = None
    published_on: date | None = None
    registration_number: str | None = None
    registration_body: str | None = None
    predecessor_uuid: str | None = None
    predecessor_version: str | None = None
    reference_quantity: Decimal
    reference_unit: str
    reference_flow_uuid: str | None = None
    reference_flow_name: str | None = None
    lifecycle_module: str
    scenario: str | None = None
    scenario_description: str | None = None
    gwp_total: Decimal
    gwp_standard: str
    gwp_biogenic: Decimal | None = None
    gwp_fossil: Decimal | None = None
    gwp_luluc: Decimal | None = None
    source_row: int

    def as_parsed_record(self) -> ParsedRecord:
        return ParsedRecord(
            data=self.model_dump(mode="json"),
            source_row=self.source_row,
            source_sheet="ÖKOBAUDAT 2024-II",
            source_table=self.lifecycle_module,
        )


class OekobaudatParser:
    required_headers: ClassVar[set[str]] = {
        "UUID",
        "Version",
        "Name (de)",
        "Name (en)",
        "Kategorie (original)",
        "Kategorie (en)",
        "Konformitaet",
        "Hintergrunddatenbank(en)",
        "Laenderkennung",
        "Typ",
        "Referenzjahr",
        "Gueltig bis",
        "URL",
        "Declaration owner",
        "Veroeffentlicht am",
        "Registrierungsnummer",
        "Registrierungsstelle",
        "UUID des Vorgaengers",
        "Version des Vorgaengers",
        "Bezugsgroesse",
        "Bezugseinheit",
        "Referenzfluss-UUID",
        "Referenzfluss-Name",
        "Modul",
        "Szenario",
        "Szenariobeschreibung",
        "GWP",
        "GWPtotal (A2)",
        "GWPbiogenic (A2)",
        "GWPfossil (A2)",
        "GWPluluc (A2)",
    }

    def __init__(self) -> None:
        self.metrics: dict[str, int] = {}

    def parse(self, path: Path) -> tuple[OekobaudatRow, ...]:
        rows: list[OekobaudatRow] = []
        input_rows = 0
        excluded_missing_total = 0
        excluded_missing_reference = 0
        with path.open(encoding="iso-8859-1", newline="") as source_file:
            reader = csv.DictReader(source_file, delimiter=";")
            headers = set(reader.fieldnames or ())
            missing_headers = self.required_headers - headers
            if missing_headers:
                raise PermanentIngestionError(
                    "ÖKOBAUDAT CSV schema changed; missing headers: "
                    + ", ".join(sorted(missing_headers))
                )
            for source_row, values in enumerate(reader, start=2):
                input_rows += 1
                gwp_a2 = self._decimal(values["GWPtotal (A2)"])
                gwp_a1 = self._decimal(values["GWP"])
                if gwp_a2 is None and gwp_a1 is None:
                    excluded_missing_total += 1
                    continue
                quantity = self._decimal(values["Bezugsgroesse"])
                reference_unit = self._text(values["Bezugseinheit"])
                if quantity is None or reference_unit is None:
                    excluded_missing_reference += 1
                    continue
                if quantity <= 0:
                    raise PermanentIngestionError(
                        f"ÖKOBAUDAT row {source_row} has a non-positive reference quantity"
                    )
                reference_year = self._integer(values["Referenzjahr"])
                if reference_year is None:
                    raise PermanentIngestionError(
                        f"ÖKOBAUDAT row {source_row} has no reference year"
                    )
                dataset_uuid = self._required(values["UUID"], "UUID", source_row)
                version = self._required(values["Version"], "Version", source_row)
                name_de = self._text(values["Name (de)"])
                name_en = self._text(values["Name (en)"])
                if name_de is None and name_en is None:
                    raise PermanentIngestionError(
                        f"ÖKOBAUDAT row {source_row} has no German or English name"
                    )
                module = self._required(values["Modul"], "Modul", source_row)
                conformity = self._required(
                    values["Konformitaet"], "Konformitaet", source_row
                )
                rows.append(
                    OekobaudatRow(
                        dataset_uuid=dataset_uuid,
                        dataset_record_version=version,
                        name_de=name_de,
                        name_en=name_en,
                        category_original=self._text(values["Kategorie (original)"]),
                        category_en=self._text(values["Kategorie (en)"]),
                        conformity=conformity,
                        background_databases=self._text(values["Hintergrunddatenbank(en)"]),
                        geography_code=self._required(
                            values["Laenderkennung"], "Laenderkennung", source_row
                        ),
                        dataset_type=self._required(values["Typ"], "Typ", source_row),
                        reference_year=reference_year,
                        valid_until_year=self._integer(values["Gueltig bis"]),
                        original_url=self._required(values["URL"], "URL", source_row),
                        declaration_owner=self._text(values["Declaration owner"]),
                        published_on=self._date(values["Veroeffentlicht am"]),
                        registration_number=self._text(values["Registrierungsnummer"]),
                        registration_body=self._text(values["Registrierungsstelle"]),
                        predecessor_uuid=self._text(values["UUID des Vorgaengers"]),
                        predecessor_version=self._text(values["Version des Vorgaengers"]),
                        reference_quantity=quantity,
                        reference_unit=reference_unit,
                        reference_flow_uuid=self._text(values["Referenzfluss-UUID"]),
                        reference_flow_name=self._text(values["Referenzfluss-Name"]),
                        lifecycle_module=module,
                        scenario=self._text(values["Szenario"]),
                        scenario_description=self._text(values["Szenariobeschreibung"]),
                        gwp_total=gwp_a2 if gwp_a2 is not None else gwp_a1,
                        gwp_standard="EN 15804+A2" if gwp_a2 is not None else "EN 15804+A1",
                        gwp_biogenic=self._decimal(values["GWPbiogenic (A2)"]),
                        gwp_fossil=self._decimal(values["GWPfossil (A2)"]),
                        gwp_luluc=self._decimal(values["GWPluluc (A2)"]),
                        source_row=source_row,
                    )
                )
        if not rows:
            raise PermanentIngestionError("ÖKOBAUDAT CSV produced no GWP result rows")
        self.metrics = {
            "input_rows": input_rows,
            "parsed_rows": len(rows),
            "excluded_missing_total_gwp": excluded_missing_total,
            "excluded_missing_reference": excluded_missing_reference,
            "a1_gwp_rows": sum(row.gwp_standard.endswith("+A1") for row in rows),
            "a2_gwp_rows": sum(row.gwp_standard.endswith("+A2") for row in rows),
            "datasets_with_gwp": len({row.dataset_uuid for row in rows}),
        }
        return tuple(rows)

    @staticmethod
    def _text(value: object) -> str | None:
        if value is None:
            return None
        text = " ".join(str(value).split())
        return text or None

    @classmethod
    def _required(cls, value: object, field: str, row: int) -> str:
        text = cls._text(value)
        if text is None:
            raise PermanentIngestionError(f"ÖKOBAUDAT row {row} has no {field}")
        return text

    @staticmethod
    def _decimal(value: object) -> Decimal | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            result = Decimal(text)
        except InvalidOperation as error:
            raise PermanentIngestionError(f"invalid ÖKOBAUDAT decimal: {text}") from error
        if not result.is_finite():
            raise PermanentIngestionError(f"non-finite ÖKOBAUDAT decimal: {text}")
        return result

    @staticmethod
    def _integer(value: object) -> int | None:
        if value is None or not str(value).strip():
            return None
        try:
            return int(str(value).strip())
        except ValueError as error:
            raise PermanentIngestionError(f"invalid ÖKOBAUDAT integer: {value}") from error

    @staticmethod
    def _date(value: object) -> date | None:
        if value is None or not str(value).strip():
            return None
        try:
            return date.fromisoformat(str(value).strip())
        except ValueError as error:
            raise PermanentIngestionError(f"invalid ÖKOBAUDAT date: {value}") from error
