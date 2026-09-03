from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import ClassVar, Literal

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, ConfigDict, Field

from atlas.domain.enums import EnvironmentalEntityType
from atlas.domain.models import ParsedRecord
from atlas.ingestion.errors import PermanentIngestionError

GasCode = Literal["CO2", "CH4", "N2O", "CO2e"]


class CanadaFactorRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    record_type: Literal["factor"] = "factor"
    table_number: str
    table_title: str
    source_row: int = Field(ge=1)
    source_column: int = Field(ge=2)
    name: str
    category: str
    variant: str | None = None
    gas: GasCode
    value: Decimal
    original_unit: str
    reference_year: int
    valid_from_year: int
    valid_to_year: int
    geography_name: str | None = None
    attributes: dict[str, str | bool | int | None] = Field(default_factory=dict)

    def as_parsed_record(self) -> ParsedRecord:
        return ParsedRecord(
            data=self.model_dump(mode="json"),
            source_row=self.source_row,
            source_table=f"Table {self.table_number}",
        )


class CanadaObservationRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    record_type: Literal["observation"] = "observation"
    table_number: str
    table_title: str
    source_row: int = Field(ge=1)
    source_column: int = Field(ge=2)
    name: str
    parameter_code: str
    value: Decimal
    unit: str
    entity_type: EnvironmentalEntityType
    protocol: str
    valid_from_year: int
    original_column_name: str

    def as_parsed_record(self) -> ParsedRecord:
        return ParsedRecord(
            data=self.model_dump(mode="json"),
            source_row=self.source_row,
            source_table=f"Table {self.table_number}",
        )


class CanadaDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str
    published_on: str
    factors: tuple[CanadaFactorRow, ...]
    observations: tuple[CanadaObservationRow, ...]

    @property
    def parsed_records(self) -> tuple[ParsedRecord, ...]:
        return tuple(
            [row.as_parsed_record() for row in self.factors]
            + [row.as_parsed_record() for row in self.observations]
        )


class CanadaParser:
    VERSION = "3.0"
    PUBLISHED_ON = "October 24, 2025"
    EXPECTED_TABLES: ClassVar[tuple[str, ...]] = (
        "1.1",
        "1.2",
        "1.3",
        "2.1",
        "2.2",
        "2.3",
        "3.1",
        "3.2",
        "3.3",
        "4.1",
        "4.2",
        "4.3",
        "5.1",
        "5.2",
        "5.3",
        "6.1",
        "6.2",
        "6.3",
        "7",
        "8",
        "9",
        "10",
        "11",
        "12",
    )
    EXPECTED_COLUMN_COUNTS: ClassVar[dict[str, int]] = {
        "1.1": 3,
        "1.2": 3,
        "1.3": 3,
        "2.1": 3,
        "2.2": 3,
        "2.3": 3,
        "3.1": 4,
        "3.2": 4,
        "3.3": 4,
        "4.1": 4,
        "4.2": 4,
        "4.3": 4,
        "5.1": 2,
        "5.2": 2,
        "5.3": 2,
        "6.1": 2,
        "6.2": 2,
        "6.3": 2,
        "7": 2,
        "8": 2,
        "9": 2,
        "10": 2,
        "11": 5,
        "12": 2,
    }

    def __init__(self) -> None:
        self.metrics: dict[str, int] = {}

    def parse(self, path: Path) -> CanadaDocument:
        try:
            content = path.read_text(encoding="utf-8")
            soup = BeautifulSoup(content, "html.parser")
        except (OSError, UnicodeError) as error:
            raise PermanentIngestionError("Canada Version 3.0 HTML is unreadable") from error
        self._assert_document_contract(soup)
        tables = self._data_tables(soup)
        factors: list[CanadaFactorRow] = []
        observations: list[CanadaObservationRow] = []
        for number, table in tables.items():
            if number in {"7", "8", "9", "10", "11", "12"}:
                observations.extend(self._observation_rows(number, table))
            else:
                factors.extend(self._factor_rows(number, table))
        if not factors or not observations:
            raise PermanentIngestionError("Canada Version 3.0 produced incomplete records")
        family_counts = Counter(row.table_number.split(".", 1)[0] for row in factors)
        observation_counts = Counter(row.table_number for row in observations)
        self.metrics = {
            "parsed_rows": len(factors) + len(observations),
            "parsed_factor_rows": len(factors),
            "parsed_observations": len(observations),
            "source_tables": len(tables),
            **{
                f"table_{family}_factors": count
                for family, count in sorted(family_counts.items())
            },
            **{
                f"table_{number}_observations": count
                for number, count in sorted(observation_counts.items())
            },
        }
        return CanadaDocument(
            version=self.VERSION,
            published_on="2025-10-24",
            factors=tuple(factors),
            observations=tuple(observations),
        )

    def stable_revision(self, path: Path) -> str:
        import hashlib
        import json

        try:
            soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        except (OSError, UnicodeError) as error:
            raise PermanentIngestionError("Canada Version 3.0 HTML is unreadable") from error
        self._assert_document_contract(soup)
        tables = self._data_tables(soup)
        payload = {
            "version": self.VERSION,
            "published_on": self.PUBLISHED_ON,
            "tables": [
                {
                    "number": number,
                    "caption": self._clean_text(table.find("caption")),
                    "headers": self._headers(table),
                    "rows": [self._cells(row) for row in table.select("tbody tr")],
                }
                for number, table in tables.items()
            ],
        }
        stable = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(stable).hexdigest()

    def _assert_document_contract(self, soup: BeautifulSoup) -> None:
        heading = soup.find("h1")
        page_text = self._clean_text(soup)
        if heading is None or self._clean_text(heading) != "Emission factors and reference values":
            raise PermanentIngestionError("Canada emission-factor document title changed")
        if f"Version {self.VERSION}" not in page_text or self.PUBLISHED_ON not in page_text:
            raise PermanentIngestionError("Canada emission-factor document version changed")

    def _data_tables(self, soup: BeautifulSoup) -> dict[str, Tag]:
        result: dict[str, Tag] = {}
        for table in soup.find_all("table"):
            caption = table.find("caption")
            if caption is None:
                continue
            match = re.match(r"Table\s+(\d+(?:\.\d+)?):", self._clean_text(caption))
            if match is None:
                continue
            number = match.group(1)
            if number in result:
                raise PermanentIngestionError(f"duplicate Canada source table: {number}")
            result[number] = table
        if tuple(result) != self.EXPECTED_TABLES:
            raise PermanentIngestionError(
                "Canada source tables changed: "
                f"expected {self.EXPECTED_TABLES}, got {tuple(result)}"
            )
        for number, table in result.items():
            headers = self._headers(table)
            if len(headers) != self.EXPECTED_COLUMN_COUNTS[number]:
                raise PermanentIngestionError(
                    f"Canada Table {number} column count changed: {len(headers)}"
                )
        return result

    def _factor_rows(self, number: str, table: Tag) -> list[CanadaFactorRow]:
        family = int(number.split(".", 1)[0])
        title = self._clean_text(table.find("caption"))
        headers = self._headers(table)
        valid_from, valid_to = self._validity(number)
        rows: list[CanadaFactorRow] = []
        for source_row, row in enumerate(table.select("tbody tr"), 1):
            cells = row.find_all(["th", "td"], recursive=False)
            values = [self._clean_text(cell) for cell in cells]
            if len(values) != len(headers):
                raise PermanentIngestionError(
                    f"Canada Table {number} row {source_row} width changed"
                )
            name = values[0]
            for column_index, (cell, raw_value) in enumerate(
                zip(cells[1:], values[1:], strict=True), start=2
            ):
                value = self._decimal(raw_value)
                if value is None:
                    continue
                gas, variant, category, geography = self._factor_semantics(
                    family, name, headers[column_index - 1]
                )
                rows.append(
                    CanadaFactorRow(
                        table_number=number,
                        table_title=title,
                        source_row=source_row,
                        source_column=column_index,
                        name=name,
                        category=category,
                        variant=variant,
                        gas=gas,
                        value=value,
                        original_unit=self._original_unit(
                            family, gas, self._clean_text(cell, keep_footnotes=True)
                        ),
                        reference_year=valid_from,
                        valid_from_year=valid_from,
                        valid_to_year=valid_to,
                        geography_name=geography,
                        attributes={
                            "regulatory_parameter": self._parameter(family, gas),
                            "general_offset_factor": True,
                            "gwp_not_applied": gas in {"CH4", "N2O"},
                        },
                    )
                )
        return rows

    def _observation_rows(self, number: str, table: Tag) -> list[CanadaObservationRow]:
        title = self._clean_text(table.find("caption"))
        headers = self._headers(table)
        protocol, valid_from = self._observation_context(number)
        parameter_codes = self._observation_parameter_codes(number, len(headers) - 1)
        rows: list[CanadaObservationRow] = []
        for source_row, row in enumerate(table.select("tbody tr"), 1):
            values = self._cells(row)
            if len(values) != len(headers):
                raise PermanentIngestionError(
                    f"Canada Table {number} row {source_row} width changed"
                )
            for column_index, parameter_code in enumerate(parameter_codes, 2):
                value = self._decimal(values[column_index - 1])
                if value is None:
                    raise PermanentIngestionError(
                        f"Canada Table {number} observation is non-numeric"
                    )
                rows.append(
                    CanadaObservationRow(
                        table_number=number,
                        table_title=title,
                        source_row=source_row,
                        source_column=column_index,
                        name=f"{values[0]} — {parameter_code}",
                        parameter_code=parameter_code,
                        value=value,
                        unit="%" if number == "7" else "dimensionless",
                        entity_type=(
                            EnvironmentalEntityType.REFERENCE_VALUE
                            if number in {"7", "8"}
                            else EnvironmentalEntityType.CALCULATION_PARAMETER
                        ),
                        protocol=protocol,
                        valid_from_year=valid_from,
                        original_column_name=headers[column_index - 1],
                    )
                )
        return rows

    @staticmethod
    def _factor_semantics(
        family: int, name: str, column_header: str
    ) -> tuple[GasCode, str | None, str, str | None]:
        if family == 1:
            return "CO2", column_header.split("Footnote", 1)[0].strip(" *"), "Natural gas", name
        if family == 2:
            gas: GasCode = "CH4" if "CH 4" in column_header else "N2O"
            geography = None
            for candidate in CanadaParser.PROVINCES:
                if name.endswith(candidate):
                    geography = candidate
                    break
            if name.endswith("Other provinces and territories"):
                geography = "Other provinces and territories"
            return gas, name, "Natural gas", geography
        if family == 3:
            gas = CanadaParser._gas_from_header(column_header)
            return gas, name, "Natural gas liquids", None
        if family == 4:
            gas = CanadaParser._gas_from_header(column_header)
            return gas, name, "Refined petroleum products", None
        if family == 5:
            return "CO2e", "Consumption intensity", "Electricity", name
        if family == 6:
            return "N2O", name, "Biogas combustion", None
        raise PermanentIngestionError(f"unsupported Canada factor family: {family}")

    PROVINCES: ClassVar[tuple[str, ...]] = (
        "Newfoundland and Labrador",
        "Northwest Territories",
        "Prince Edward Island",
        "British Columbia",
        "New Brunswick",
        "Nova Scotia",
        "Saskatchewan",
        "Manitoba",
        "Ontario",
        "Quebec",
        "Alberta",
        "Nunavut",
        "Yukon",
    )

    @staticmethod
    def _gas_from_header(header: str) -> GasCode:
        if "CO 2" in header:
            return "CO2"
        if "CH 4" in header:
            return "CH4"
        if "N 2 O" in header:
            return "N2O"
        raise PermanentIngestionError(f"Canada gas header changed: {header}")

    @staticmethod
    def _parameter(family: int, gas: GasCode) -> str:
        if family == 5:
            return "EF_grid"
        return f"EF_{gas}"

    @staticmethod
    def _validity(number: str) -> tuple[int, int]:
        suffix = number.split(".", 1)[1]
        return {"1": (2023, 2024), "2": (2025, 2025), "3": (2026, 2026)}[suffix]

    @staticmethod
    def _original_unit(family: int, gas: GasCode, cell_text: str) -> str:
        if family in {1, 2}:
            return f"g{gas}/m3"
        if family in {3, 4}:
            denominator = "m3" if re.search(r"g/m\s*3", cell_text) else "L"
            return f"g{gas}/{denominator}"
        if family == 5:
            return "gCO2e/kWh"
        if family == 6:
            return "kgN2O/tCH4"
        raise PermanentIngestionError(f"unsupported Canada unit family: {family}")

    @staticmethod
    def _observation_context(number: str) -> tuple[str, int]:
        if number in {"7", "8"}:
            return "Improved Forest Management on Private Land", 2024
        return "Reducing Enteric Methane Emissions from Beef Cattle", 2025

    @staticmethod
    def _observation_parameter_codes(number: str, count: int) -> tuple[str, ...]:
        codes = {
            "7": ("PC_i,C",),
            "8": ("SF_j",),
            "9": ("Y_m",),
            "10": ("EF_lip",),
            "11": ("MCF", "EF_MS", "Frac_v", "Frac_L"),
            "12": ("EF_V",),
        }[number]
        if len(codes) != count:
            raise PermanentIngestionError(f"Canada Table {number} parameter columns changed")
        return codes

    @classmethod
    def _headers(cls, table: Tag) -> list[str]:
        return [cls._clean_text(cell) for cell in table.select("thead th")]

    @classmethod
    def _cells(cls, row: Tag) -> list[str]:
        return [
            cls._clean_text(cell)
            for cell in row.find_all(["th", "td"], recursive=False)
        ]

    @staticmethod
    def _clean_text(node: Tag | BeautifulSoup | None, *, keep_footnotes: bool = False) -> str:
        if node is None:
            return ""
        text = " ".join(node.get_text(" ", strip=True).replace("\u00a0", " ").split())
        if not keep_footnotes:
            text = re.sub(r"\s*Footnote\s+\d+", "", text)
        return text.strip()

    @staticmethod
    def _decimal(value: str) -> Decimal | None:
        if value.strip() in {"", "-", "—"}:
            return None
        cleaned = re.sub(r"\s*Footnote\s+\d+.*$", "", value).strip()
        match = re.match(r"[-+]?\d[\d\s\u00a0]*(?:\.\d+)?", cleaned)
        if match is None:
            return None
        try:
            return Decimal(re.sub(r"[\s\u00a0]", "", match.group(0)))
        except InvalidOperation:
            return None
