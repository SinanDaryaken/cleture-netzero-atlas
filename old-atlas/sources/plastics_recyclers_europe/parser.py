from __future__ import annotations

import re
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import ClassVar

import pdfplumber
from pydantic import BaseModel, ConfigDict

from atlas.domain.models import ParsedRecord
from atlas.ingestion.errors import PermanentIngestionError


class RecycledResinRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    polymer_key: str
    polymer_name: str
    output_form: str
    value_kgco2e_per_t_output: Decimal
    value_basis: str
    upstream_dataset: str
    source_page: int = 33
    source_table: str = "Table 28"

    def as_parsed_record(self) -> ParsedRecord:
        return ParsedRecord(
            data=self.model_dump(mode="json"),
            source_row=self.source_page,
            source_sheet=f"PDF page {self.source_page}",
            source_table=self.source_table,
        )


class PreModelParameterRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    parameter_key: str
    name: str
    value: Decimal
    unit: str
    source_category: str
    source_page: int
    source_table: str
    value_role: str
    value_basis: str

    def as_parsed_record(self) -> ParsedRecord:
        return ParsedRecord(
            data=self.model_dump(mode="json"),
            source_row=self.source_page,
            source_sheet=f"PDF page {self.source_page}",
            source_table=self.source_table,
        )


class PlasticsRecyclersEuropeDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str
    resin_results: tuple[RecycledResinRow, ...]
    parameters: tuple[PreModelParameterRow, ...]

    @property
    def parsed_records(self) -> tuple[ParsedRecord, ...]:
        records = [row.as_parsed_record() for row in self.resin_results]
        records.extend(row.as_parsed_record() for row in self.parameters)
        return tuple(records)


class PlasticsRecyclersEuropeParser:
    VERSION = "2015-05-29"
    EXPECTED_PAGES = 54
    resin_specs: ClassVar[tuple[tuple[str, str, str, str, str], ...]] = (
        (
            "pet_bottle",
            "Recycled PET bottle-grade",
            "pellets or flakes",
            "documented",
            "Wisard LCI",
        ),
        ("pet_fibre", "Recycled PET fibre-grade", "pellets or flakes", "documented", "Wisard LCI"),
        (
            "pe_hd",
            "Recycled high-density polyethylene (PE-HD)",
            "pellets or flakes",
            "documented",
            "Wisard LCI",
        ),
        (
            "pe_ld",
            "Recycled low-density polyethylene (PE-LD)",
            "pellets or flakes",
            "documented",
            "Wisard LCI",
        ),
        (
            "pp",
            "Recycled polypropylene (PP)",
            "pellets or flakes",
            "proxy_from_pe",
            "PRE assumption backed by Menikpura et al. 2014",
        ),
        (
            "ps",
            "Recycled polystyrene (PS)",
            "pellets or flakes",
            "proxy_from_pe",
            "PRE assumption backed by Menikpura et al. 2014",
        ),
        (
            "pvc",
            "Recycled polyvinyl chloride (PVC)",
            "pellets or flakes",
            "proxy_from_pe",
            "PRE assumption backed by Menikpura et al. 2014",
        ),
        (
            "other",
            "Other recycled plastic resins",
            "pellets or flakes",
            "proxy_from_pe",
            "PRE assumption in absence of resin data",
        ),
    )

    def __init__(
        self,
        *,
        page_text_extractor: Callable[[Path], tuple[str, ...]] | None = None,
    ) -> None:
        self.page_text_extractor = page_text_extractor or self._pdf_pages
        self.metrics: dict[str, int] = {}

    def parse(self, path: Path) -> PlasticsRecyclersEuropeDocument:
        try:
            pages = self.page_text_extractor(path)
        except PermanentIngestionError:
            raise
        except Exception as error:
            raise PermanentIngestionError("PRE impact assessment is not a readable PDF") from error
        self._assert_contract(pages)
        resin_values = self._table_values(
            pages[32],
            r"Direct GHG emissions\s+([0-9]+(?: [0-9]{3})?)\s*/\s*"
            r"([0-9]+(?: [0-9]{3})?)\s+([0-9]+(?: [0-9]{3})?)\s+"
            r"([0-9]+(?: [0-9]{3})?)\s+([0-9]+(?: [0-9]{3})?)\s+"
            r"([0-9]+(?: [0-9]{3})?)\s+([0-9]+(?: [0-9]{3})?)\s+"
            r"([0-9]+(?: [0-9]{3})?)\s+from recycling",
            expected=8,
            table="Table 28",
        )
        resin_results = tuple(
            RecycledResinRow(
                polymer_key=spec[0],
                polymer_name=spec[1],
                output_form=spec[2],
                value_kgco2e_per_t_output=value,
                value_basis=spec[3],
                upstream_dataset=spec[4],
            )
            for spec, value in zip(self.resin_specs, resin_values, strict=True)
        )
        parameters = self._parameters(pages)
        documented = sum(row.value_basis == "documented" for row in resin_results)
        self.metrics = {
            "parsed_rows": len(resin_results) + len(parameters),
            "recycled_resin_results": len(resin_results),
            "documented_resin_results": documented,
            "proxy_resin_results": len(resin_results) - documented,
            "calculation_parameter_rows": len(parameters),
        }
        return PlasticsRecyclersEuropeDocument(
            version=self.VERSION,
            resin_results=resin_results,
            parameters=parameters,
        )

    def _parameters(self, pages: tuple[str, ...]) -> tuple[PreModelParameterRow, ...]:
        page_32 = self._normal(pages[31])
        page_34 = self._normal(pages[33])
        page_35 = self._normal(pages[34])
        virgin_values = self._table_values(
            pages[32],
            r"Direct GHG emission from\s+([0-9]+(?: [0-9]{3})?)\s*/\s*"
            r"([0-9]+(?: [0-9]{3})?)\s+([0-9]+(?: [0-9]{3})?)\s+"
            r"([0-9]+(?: [0-9]{3})?)\s+([0-9]+(?: [0-9]{3})?)\s+"
            r"([0-9]+(?: [0-9]{3})?)\s+([0-9]+(?: [0-9]{3})?)\s+"
            r"([0-9]+(?: [0-9]{3})?)\s+virgin plastics production",
            expected=8,
            table="Table 29",
        )
        parameter_data: list[tuple[str, str, Decimal, str, str, int, str, str, str]] = [
            (
                "collection",
                "Separate collection of plastic waste",
                self._value(
                    page_32, r"emission factor resulting from these conditions is ([0-9.]+) g CO"
                ),
                "gCO2e/kg material",
                "Collection",
                32,
                "Section 5.1.1",
                "direct",
                "German-derived transport assumption",
            ),
            (
                "sorting",
                "Pre-treatment and sorting of collected plastics",
                self._value(page_32, r"emission factor at the sorting step is ([0-9.]+) kg CO2e/t"),
                "kgCO2e/t input",
                "Sorting",
                32,
                "Section 5.1.2",
                "direct",
                "PRE facility energy and EU-28 electricity model",
            ),
            (
                "transport_recycler",
                "Transport of sorted plastic waste to recyclers",
                self._value(page_32, r"to recyclers is estimated at ([0-9.]+) g CO"),
                "gCO2e/kg material",
                "Transport",
                32,
                "Section 5.1.3",
                "direct",
                "380 km France-based distance assumption",
            ),
            (
                "transport_disposal",
                "Transport of plastic waste to incineration or landfill",
                self._value(
                    page_32,
                    r"(?:2 )?incinerators or landfills is estimated at ([0-9.]+) g CO",
                ),
                "gCO2e/kg material",
                "Transport",
                32,
                "Section 5.1.3",
                "direct",
                "30 km distance assumption",
            ),
        ]
        virgin_keys = ("pet_bottle", "pet_fibre", "pe_hd", "pe_ld", "pp", "ps", "pvc", "other")
        virgin_names = (
            "PET bottle-grade",
            "PET fibre-grade",
            "PE-HD",
            "PE-LD",
            "PP",
            "PS",
            "PVC",
            "other plastic resins",
        )
        parameter_data.extend(
            (
                f"virgin_{key}",
                f"Virgin {name} production displaced by recycled plastic",
                value,
                "kgCO2e/t output",
                "Virgin plastic substitution",
                33,
                "Table 29",
                "avoided_substitution_input",
                "PlasticsEurope 2014 Eco-profile input to PRE model",
            )
            for key, name, value in zip(virgin_keys, virgin_names, virgin_values, strict=True)
        )
        parameter_data.extend(
            (
                key,
                name,
                self._value(page, pattern),
                "kgCO2e/t plastic waste",
                category,
                page_number,
                table,
                role,
                basis,
            )
            for key, name, page, pattern, category, page_number, table, role, basis in (
                (
                    "incineration",
                    "Direct incineration of plastic waste",
                    page_34,
                    r"incineration is calculated at ([0-9 ]+) kg CO",
                    "Energy recovery",
                    34,
                    "Section 5.1.5.1",
                    "direct",
                    "IPCC 2006 carbon-content calculation",
                ),
                (
                    "rdf_coincineration",
                    "Direct co-incineration of plastic waste as RDF/SRF",
                    page_34,
                    r"co-incineration of RDF is calculated at ([0-9 ]+) kg CO",
                    "Energy recovery",
                    34,
                    "Section 5.1.5.2",
                    "direct",
                    "Same plastic carbon-content calculation as incineration",
                ),
                (
                    "incineration_energy_credit",
                    "Avoided energy emissions from plastic incineration",
                    page_34,
                    r"avoided emissions from incineration is therefore estimated at "
                    r"([0-9 ]+) kg CO",
                    "Energy recovery",
                    34,
                    "Section 5.1.5.3",
                    "avoided",
                    "EU-28 electricity and heat substitution model",
                ),
                (
                    "rdf_energy_credit",
                    "Avoided fossil-fuel emissions from RDF/SRF",
                    page_34,
                    r"resulting GHG emissions factor is ([0-9 ]+) kg CO",
                    "Energy recovery",
                    34,
                    "Section 5.1.5.4",
                    "avoided",
                    "Hard coal, coke, or oil substitution model",
                ),
                (
                    "landfill",
                    "Direct plastic-waste landfilling operations",
                    page_35,
                    r"factor ([0-9 ]+) kg CO",
                    "Landfill",
                    35,
                    "Section 5.1.6",
                    "direct",
                    "Midpoint selected from published 6-16 range",
                ),
            )
        )
        rows = tuple(
            PreModelParameterRow(
                parameter_key=item[0],
                name=item[1],
                value=item[2],
                unit=item[3],
                source_category=item[4],
                source_page=item[5],
                source_table=item[6],
                value_role=item[7],
                value_basis=item[8],
            )
            for item in parameter_data
        )
        if len(rows) != 17:
            raise PermanentIngestionError(f"PRE expected 17 model parameters; found {len(rows)}")
        return rows

    @classmethod
    def _assert_contract(cls, pages: tuple[str, ...]) -> None:
        if len(pages) != cls.EXPECTED_PAGES:
            raise PermanentIngestionError(
                f"PRE PDF page count changed: expected {cls.EXPECTED_PAGES}, got {len(pages)}"
            )
        markers = {
            1: ("29 May 2015", "Increased EU Plastics Recycling Targets"),
            32: ("Plastic waste collection", "Transportation of plastics to recyclers"),
            33: ("Table 28", "Table 29"),
            34: ("Avoided emissions from RDF/SRF", "Landfilling of plastics"),
            35: ("factor 10 kg", "Assessment of scenarios"),
        }
        for page_number, expected in markers.items():
            text = cls._normal(pages[page_number - 1])
            if any(marker not in text for marker in expected):
                raise PermanentIngestionError(f"PRE PDF layout changed at page {page_number}")

    @classmethod
    def _table_values(
        cls,
        text: str,
        pattern: str,
        *,
        expected: int,
        table: str,
    ) -> tuple[Decimal, ...]:
        match = re.search(pattern, cls._normal(text))
        if match is None or len(match.groups()) != expected:
            raise PermanentIngestionError(f"PRE {table} value layout changed")
        return tuple(cls._decimal(value) for value in match.groups())

    @classmethod
    def _value(cls, text: str, pattern: str) -> Decimal:
        match = re.search(pattern, text)
        if match is None:
            raise PermanentIngestionError(f"PRE model parameter layout changed: {pattern}")
        return cls._decimal(match.group(1))

    @staticmethod
    def _decimal(value: str) -> Decimal:
        try:
            return Decimal(value.replace(" ", ""))
        except InvalidOperation as error:
            raise PermanentIngestionError(f"PRE invalid numeric value: {value}") from error

    @staticmethod
    def _normal(value: str) -> str:
        collapsed = " ".join(value.replace("CO₂", "CO2").split())
        return re.sub(r"CO\s+2", "CO2", collapsed)

    @staticmethod
    def _pdf_pages(path: Path) -> tuple[str, ...]:
        with pdfplumber.open(path) as pdf:
            return tuple(page.extract_text() or "" for page in pdf.pages)
