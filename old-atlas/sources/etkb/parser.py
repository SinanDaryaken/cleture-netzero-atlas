# ruff: noqa: RUF001 -- source contract intentionally preserves official Turkish labels.

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

import pdfplumber
from pydantic import BaseModel, ConfigDict, Field

from atlas.domain.models import ParsedRecord
from atlas.ingestion.errors import PermanentIngestionError

EtbkCategory = Literal["national_generation", "fuel_generation", "consumption_point"]


class EtkbRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    reference_year: int = Field(ge=2020, le=2200)
    category: EtbkCategory
    activity_key: str
    activity_name: str
    co2_t_per_mwh: Decimal
    co2e_t_per_mwh: Decimal
    source_page: int = Field(ge=1)
    source_table: str
    source_row: int = Field(ge=1)
    co2_column: int = Field(ge=1)
    co2e_column: int = Field(ge=1)

    def as_parsed_record(self) -> ParsedRecord:
        return ParsedRecord(
            data=self.model_dump(mode="json"),
            source_row=self.source_row,
            source_sheet=f"Page {self.source_page}",
            source_table=self.source_table,
        )


class EtkbDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    reference_year: int
    published_on: date
    calculation_revision: str
    document_number: str
    rows: tuple[EtkbRow, ...]

    @property
    def parsed_records(self) -> tuple[ParsedRecord, ...]:
        return tuple(row.as_parsed_record() for row in self.rows)


class EtkbParser:
    TITLE = "TÜRKİYE ELEKTRİK ÜRETİMİ VE ELEKTRİK TÜKETİM NOKTASI EMİSYON FAKTÖRLERİ"
    DOCUMENT_NUMBER = "ETKB-EVÇED-FRM-042 Rev.01"
    FUELS = (
        ("Linyit", "lignite"),
        ("Taş Kömürü", "hard_coal"),
        ("Asfaltit", "asphaltite"),
        ("İthal Kömür", "imported_coal"),
        ("Doğalgaz", "natural_gas"),
        ("Fuel Oil", "fuel_oil"),
        ("Motorin", "diesel"),
    )

    def __init__(self) -> None:
        self.metrics: dict[str, int] = {}

    def parse(self, path: Path) -> EtkbDocument:
        try:
            with pdfplumber.open(path) as pdf:
                if len(pdf.pages) != 2:
                    raise PermanentIngestionError(
                        f"ETKB annual PDF page count changed: {len(pdf.pages)}"
                    )
                page_tables = [page.extract_tables() for page in pdf.pages]
        except PermanentIngestionError:
            raise
        except Exception as error:
            raise PermanentIngestionError("ETKB file is not a readable annual PDF") from error

        if [len(tables) for tables in page_tables] != [3, 3]:
            raise PermanentIngestionError("ETKB annual PDF table layout changed")
        header_table, metadata_table, national_table = page_tables[0]
        repeated_header, fuel_table, consumption_table = page_tables[1]
        self._assert_document_header(header_table)
        self._assert_document_header(repeated_header)
        reference_year, published_on, calculation_revision = self._metadata(metadata_table)
        rows = [self._national_row(national_table, reference_year)]
        rows.extend(self._fuel_rows(fuel_table, reference_year))
        rows.extend(self._consumption_rows(consumption_table, reference_year))
        if len(rows) != 10:
            raise PermanentIngestionError(f"ETKB annual PDF produced {len(rows)} rows")
        self.metrics = {
            "parsed_rows": len(rows),
            "national_generation_rows": 1,
            "fuel_generation_rows": 7,
            "consumption_point_rows": 2,
            "source_tables": 3,
            "release_year": reference_year,
        }
        return EtkbDocument(
            reference_year=reference_year,
            published_on=published_on,
            calculation_revision=calculation_revision,
            document_number=self.DOCUMENT_NUMBER,
            rows=tuple(rows),
        )

    def _assert_document_header(self, table: list[list[str | None]]) -> None:
        if len(table) != 2 or len(table[0]) != 4:
            raise PermanentIngestionError("ETKB document header layout changed")
        if self._key(table[0][1]) != self._key(f"{self.TITLE} BİLGİ FORMU"):
            raise PermanentIngestionError("ETKB annual PDF title changed")
        if self._text(table[0][3]) != self.DOCUMENT_NUMBER:
            raise PermanentIngestionError("ETKB document number changed")

    def _metadata(self, table: list[list[str | None]]) -> tuple[int, date, str]:
        if len(table) != 2 or [self._key(value) for value in table[0]] != [
            "hesaplamadonemi",
            "hesaplamayayimtarihi",
            "hesaplamarevizyonno",
        ]:
            raise PermanentIngestionError("ETKB calculation metadata changed")
        try:
            reference_year = int(self._text(table[1][0]))
            published_on = datetime.strptime(self._text(table[1][1]), "%d.%m.%Y").date()
            revision = self._text(table[1][2])
        except (ValueError, IndexError) as error:
            raise PermanentIngestionError("ETKB calculation metadata is invalid") from error
        if not re.fullmatch(r"\d{2}", revision):
            raise PermanentIngestionError("ETKB calculation revision changed")
        return reference_year, published_on, revision

    def _national_row(self, table: list[list[str | None]], year: int) -> EtkbRow:
        self._assert_factor_headers(table, with_fuel=False)
        if len(table) != 2 or self._text(table[1][1]) != str(year):
            raise PermanentIngestionError("ETKB national generation row changed")
        return EtkbRow(
            reference_year=year,
            category="national_generation",
            activity_key="turkiye_gross_generation",
            activity_name="Türkiye Geneli Elektrik Üretimi",
            co2_t_per_mwh=self._decimal(table[1][2]),
            co2e_t_per_mwh=self._decimal(table[1][3]),
            source_page=1,
            source_table="Elektrik Üretimi Emisyon Faktörü",
            source_row=2,
            co2_column=3,
            co2e_column=4,
        )

    def _fuel_rows(self, table: list[list[str | None]], year: int) -> list[EtkbRow]:
        self._assert_factor_headers(table, with_fuel=True)
        if len(table) != 8:
            raise PermanentIngestionError("ETKB fuel-generation row count changed")
        result: list[EtkbRow] = []
        for source_row, ((expected_name, key), values) in enumerate(
            zip(self.FUELS, table[1:], strict=True), start=2
        ):
            row_year = self._text(values[1]) or str(year)
            if self._text(values[2]) != expected_name or row_year != str(year):
                raise PermanentIngestionError(
                    f"ETKB fuel-generation contract changed at row {source_row}"
                )
            result.append(
                EtkbRow(
                    reference_year=year,
                    category="fuel_generation",
                    activity_key=f"fuel_{key}",
                    activity_name=f"Elektrik Üretimi — {expected_name}",
                    co2_t_per_mwh=self._decimal(values[3]),
                    co2e_t_per_mwh=self._decimal(values[4]),
                    source_page=2,
                    source_table="Yakıtlara Göre Elektrik Üretim Emisyon Faktörleri",
                    source_row=source_row,
                    co2_column=4,
                    co2e_column=5,
                )
            )
        return result

    def _consumption_rows(
        self, table: list[list[str | None]], year: int
    ) -> list[EtkbRow]:
        self._assert_factor_headers(table, with_fuel=False)
        if len(table) != 3:
            raise PermanentIngestionError("ETKB consumption-point row count changed")
        expected = (
            ("İletim Hattından Bağlı Tüketim Noktası Emisyon Faktörü", "transmission"),
            ("Dağıtım Hattından Bağlı Tüketim Noktası Emisyon Faktörü", "distribution"),
        )
        result: list[EtkbRow] = []
        for source_row, ((expected_name, key), values) in enumerate(
            zip(expected, table[1:], strict=True), start=2
        ):
            if self._text(values[0]) != expected_name or self._text(values[1]) != str(year):
                raise PermanentIngestionError(
                    f"ETKB consumption-point contract changed at row {source_row}"
                )
            result.append(
                EtkbRow(
                    reference_year=year,
                    category="consumption_point",
                    activity_key=f"consumption_{key}",
                    activity_name=expected_name.removesuffix(" Emisyon Faktörü"),
                    co2_t_per_mwh=self._decimal(values[2]),
                    co2e_t_per_mwh=self._decimal(values[3]),
                    source_page=2,
                    source_table="Elektrik Tüketim Noktası Emisyon Faktörleri",
                    source_row=source_row,
                    co2_column=3,
                    co2e_column=4,
                )
            )
        return result

    def _assert_factor_headers(
        self, table: list[list[str | None]], *, with_fuel: bool
    ) -> None:
        if not table:
            raise PermanentIngestionError("ETKB factor table is empty")
        expected = ["faktorturu", "yili"]
        if with_fuel:
            expected.append("yakitturu")
        expected.extend(["degeritco2mwh", "degeritco2esdmwh"])
        actual = [self._key(value) for value in table[0]]
        if actual != expected:
            raise PermanentIngestionError(
                f"ETKB factor table headers changed: expected {expected}, got {actual}"
            )

    @staticmethod
    def _text(value: Any) -> str:
        if value is None:
            return ""
        return " ".join(str(value).replace("\n", " ").split())

    @classmethod
    def _key(cls, value: Any) -> str:
        text = cls._text(value).casefold()
        text = text.replace("₂", "2").replace("-eşd.", "esd")
        text = text.translate(str.maketrans("çğıöşü", "cgiosu"))
        key = re.sub(r"[^a-z0-9]+", "", text)
        return {
            "degeritcomwh2": "degeritco2mwh",
            "degeritcoesdmwh2": "degeritco2esdmwh",
        }.get(key, key)

    @classmethod
    def _decimal(cls, value: Any) -> Decimal:
        try:
            return Decimal(cls._text(value).replace(".", "").replace(",", "."))
        except InvalidOperation as error:
            raise PermanentIngestionError(f"invalid ETKB factor value: {value}") from error
