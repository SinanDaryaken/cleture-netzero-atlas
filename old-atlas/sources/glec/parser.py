from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pdfplumber
from pydantic import BaseModel, ConfigDict, Field

from atlas.domain.models import ParsedRecord
from atlas.ingestion.errors import PermanentIngestionError


class GlecFuelRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    geography_code: str
    geography_name: str
    energy_carrier: str
    application: str | None = None
    ttw_g_co2e_per_mj: Decimal
    wtw_g_co2e_per_mj: Decimal
    source_page: int
    source_table: str

    def as_parsed_record(self) -> ParsedRecord:
        return ParsedRecord(
            data=self.model_dump(mode="json"),
            source_row=self.source_page,
            source_sheet=f"PDF page {self.source_page}",
            source_table=self.source_table,
        )


class GlecIntensityRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: str
    geography_code: str
    geography_name: str
    category: str
    detail: str | None = None
    fuel: str | None = None
    activity_unit: str
    wtw_value: Decimal
    wtt_value: Decimal | None = None
    ttw_value: Decimal | None = None
    aggregate_value: Decimal | None = None
    source_unit: str
    source_page: int
    source_table: str
    attributes: dict[str, str] = Field(default_factory=dict)

    def as_parsed_record(self) -> ParsedRecord:
        return ParsedRecord(
            data=self.model_dump(mode="json"),
            source_row=self.source_page,
            source_sheet=f"PDF page {self.source_page}",
            source_table=self.source_table,
        )


class GlecRefrigerantRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    refrigerant: str
    chemical_formula: str | None = None
    alternative_name: str | None = None
    gwp100_ar6: Decimal | None = None
    source_page: int = 114
    source_table: str = "Module 3 Table 2"

    def as_parsed_record(self) -> ParsedRecord:
        return ParsedRecord(
            data=self.model_dump(mode="json"),
            source_row=self.source_page,
            source_sheet=f"PDF page {self.source_page}",
            source_table=self.source_table,
        )


class GlecParameterRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    equipment_type: str
    value: Decimal
    unit: str
    source_page: int = 113
    source_table: str = "Module 3 Table 1"

    def as_parsed_record(self) -> ParsedRecord:
        return ParsedRecord(
            data=self.model_dump(mode="json"),
            source_row=self.source_page,
            source_sheet=f"PDF page {self.source_page}",
            source_table=self.source_table,
        )


class GlecDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str
    fuels: tuple[GlecFuelRow, ...]
    intensities: tuple[GlecIntensityRow, ...]
    refrigerants: tuple[GlecRefrigerantRow, ...]
    parameters: tuple[GlecParameterRow, ...]

    @property
    def parsed_records(self) -> tuple[ParsedRecord, ...]:
        rows: list[ParsedRecord] = []
        for collection in (self.fuels, self.intensities, self.refrigerants, self.parameters):
            rows.extend(row.as_parsed_record() for row in collection)
        return tuple(rows)


@dataclass(frozen=True)
class _TableSpec:
    page: int
    name: str
    columns: tuple[float, ...]
    anchor: int
    y_min: float
    y_max: float


class GlecParser:
    """Parse the audited table layout of the GLEC Framework v3.2 PDF."""

    VERSION = "3.2"
    EXPECTED_PAGES = 183

    def __init__(self) -> None:
        self.metrics: dict[str, int] = {}

    def parse(self, path: Path) -> GlecDocument:
        try:
            with pdfplumber.open(path) as pdf:
                self._assert_contract(pdf)
                word_cache: dict[int, list[dict[str, Any]]] = {}

                def cells(spec: _TableSpec) -> list[list[str]]:
                    page = pdf.pages[spec.page - 1]
                    words = word_cache.setdefault(
                        spec.page,
                        page.extract_words(keep_blank_chars=False, use_text_flow=False),
                    )
                    return self._extract_cells(page, words, spec)

                fuels = self._parse_fuels(cells)
                intensities = self._parse_intensities(cells)
                refrigerants = self._parse_refrigerants(cells)
                parameters = self._parse_parameters(cells)
        except PermanentIngestionError:
            raise
        except Exception as error:
            raise PermanentIngestionError("GLEC file is not a readable v3.2 PDF") from error

        if not fuels or not intensities or not refrigerants:
            raise PermanentIngestionError("GLEC factor tables produced no records")
        self.metrics = {
            "parsed_rows": len(fuels) + len(intensities) + len(refrigerants) + len(parameters),
            "fuel_rows": len(fuels),
            "transport_intensity_rows": len(intensities),
            "refrigerant_rows": len(refrigerants),
            "calculation_parameter_rows": len(parameters),
        }
        return GlecDocument(
            version=self.VERSION,
            fuels=tuple(fuels),
            intensities=tuple(intensities),
            refrigerants=tuple(refrigerants),
            parameters=tuple(parameters),
        )

    @classmethod
    def _assert_contract(cls, pdf: Any) -> None:
        if len(pdf.pages) != cls.EXPECTED_PAGES:
            raise PermanentIngestionError(
                f"GLEC PDF page count changed: expected {cls.EXPECTED_PAGES}, got {len(pdf.pages)}"
            )
        markers = {
            1: "V3.2",
            77: "Emission factors: European sources",
            94: "Air transport emission intensity factors",
            114: "Refrigerant emission factors",
        }
        for page_number, marker in markers.items():
            text = pdf.pages[page_number - 1].extract_text() or ""
            if marker not in " ".join(text.split()):
                raise PermanentIngestionError(f"GLEC v3.2 PDF layout changed at page {page_number}")

    @classmethod
    def _extract_cells(
        cls,
        page: Any,
        words: list[dict[str, Any]],
        spec: _TableSpec,
    ) -> list[list[str]]:
        left = spec.columns[spec.anchor]
        right = spec.columns[spec.anchor + 1]
        center = (left + right) / 2
        lines = sorted(
            {
                round(float(line["top"]), 2)
                for line in page.lines
                if abs(float(line["top"]) - float(line["bottom"])) < 0.2
                and float(line["x0"]) <= center <= float(line["x1"])
            }
        )
        anchors = [
            word
            for word in words
            if left <= cls._center(word) < right
            and spec.y_min <= float(word["top"]) < spec.y_max
            and cls._is_number_or_dash(str(word["text"]))
        ]
        bands: set[tuple[float, float]] = set()
        for anchor in anchors:
            prior = [line for line in lines if line < float(anchor["top"])]
            following = [line for line in lines if line > float(anchor["bottom"])]
            top = max(prior) if prior else spec.y_min
            bottom = min(following) if following else spec.y_max
            if top < bottom:
                bands.add((top, bottom))

        rows: list[list[str]] = []
        for top, bottom in sorted(bands):
            row: list[str] = []
            for x0, x1 in zip(spec.columns, spec.columns[1:], strict=False):
                cell_words = [
                    word
                    for word in words
                    if top + 0.2 <= float(word["top"]) < bottom - 0.2
                    and x0 <= cls._center(word) < x1
                ]
                cell_words.sort(key=lambda word: (round(float(word["top"]), 1), float(word["x0"])))
                row.append(" ".join(str(word["text"]) for word in cell_words).strip())
            rows.append(row)
        return rows

    def _parse_fuels(self, cells: Any) -> list[GlecFuelRow]:
        rows: list[GlecFuelRow] = []
        standard_specs = (
            (
                _TableSpec(
                    77,
                    "European fuel factors",
                    (28.3, 125, 200.6, 250.2, 290.3, 364, 437.7, 511.4, 585.1, 658.8, 732, 811),
                    5,
                    210,
                    499,
                ),
                "EU",
                "Europe",
                0,
                1,
                4,
                5,
            ),
            (
                _TableSpec(
                    78,
                    "European fuel factors",
                    (28.3, 125, 200.6, 250.2, 290.3, 364, 437.7, 511.4, 585.1, 658.8, 732, 811),
                    5,
                    210,
                    294,
                ),
                "EU",
                "Europe",
                0,
                1,
                4,
                5,
            ),
            (
                _TableSpec(
                    79,
                    "North American fuel factors",
                    (28.3, 190.6, 239.5, 279.6, 353.3, 428, 501, 574.7, 649.1, 726.5, 811),
                    4,
                    210,
                    395,
                ),
                "NA",
                "North America",
                0,
                None,
                3,
                4,
            ),
            (
                _TableSpec(
                    80,
                    "China fuel factors",
                    (28.3, 190.6, 264.3, 306.9, 381, 455, 528.7, 602.4, 676.1, 739.8, 811),
                    4,
                    220,
                    402,
                ),
                "CN",
                "China",
                0,
                None,
                3,
                4,
            ),
            (
                _TableSpec(
                    81,
                    "India fuel factors",
                    (28.3, 190.6, 255.8, 306.9, 381, 455, 528.7, 602.4, 676.1, 739.8, 811),
                    4,
                    220,
                    387,
                ),
                "IN",
                "India",
                0,
                None,
                3,
                4,
            ),
            (
                _TableSpec(
                    85,
                    "Marine fuel factors",
                    (28.3, 87.1, 212.9, 256, 329.7, 403.9, 477.6, 552, 625.9, 699.3, 811),
                    5,
                    130,
                    571,
                ),
                "GLOBAL",
                "Global",
                0,
                1,
                3,
                4,
            ),
            (
                _TableSpec(
                    87,
                    "Air fuel factors",
                    (26.4, 136.2, 210.3, 284.3, 358, 431.7, 505.4, 579.6, 653.4, 727.1, 811),
                    4,
                    180,
                    226,
                ),
                "GLOBAL",
                "Global",
                0,
                None,
                3,
                4,
            ),
        )
        for (
            spec,
            geography_code,
            geography_name,
            name_col,
            app_col,
            ttw_col,
            wtw_col,
        ) in standard_specs:
            primary = ""
            for values in cells(spec):
                primary = self._clean(values[name_col]) or primary
                application = self._clean(values[app_col]) if app_col is not None else None
                name = primary
                if spec.page == 85 and application:
                    name = primary or application
                ttw = self._number(values[ttw_col])
                wtw = self._number(values[wtw_col])
                if not name or ttw is None or wtw is None:
                    continue
                rows.append(
                    GlecFuelRow(
                        geography_code=geography_code,
                        geography_name=geography_name,
                        energy_carrier=name,
                        application=application,
                        ttw_g_co2e_per_mj=ttw,
                        wtw_g_co2e_per_mj=wtw,
                        source_page=spec.page,
                        source_table=spec.name,
                    )
                )

        blend_specs = (
            (
                _TableSpec(
                    88,
                    "Diesel-biofuel blends Europe",
                    (28.3, 159.4, 214.7, 270.1, 326, 379.1, 434.4, 488.3, 542.4, 598.4, 650),
                    6,
                    340,
                    529,
                ),
                "EU",
                "Europe",
            ),
            (
                _TableSpec(
                    89,
                    "Gasoline-ethanol blends Europe",
                    (28.3, 159.4, 214.7, 270.1, 326, 379.1, 434.4, 488.3, 542.4, 598.4, 650),
                    6,
                    140,
                    320,
                ),
                "EU",
                "Europe",
            ),
            (
                _TableSpec(
                    89,
                    "Diesel-HVO blends Europe",
                    (28.3, 159.4, 214.7, 270.1, 326, 379.1, 434.4, 488.3, 542.4, 598.4, 650),
                    6,
                    330,
                    438,
                ),
                "EU",
                "Europe",
            ),
            (
                _TableSpec(
                    89,
                    "Diesel-HVO blends North America",
                    (28.3, 159.4, 214.7, 270.1, 326, 379.1, 434.4, 488.3, 542.4, 598.4, 650),
                    6,
                    455,
                    562,
                ),
                "NA",
                "North America",
            ),
            (
                _TableSpec(
                    90,
                    "Diesel-biofuel blends North America",
                    (28.3, 159.4, 214.7, 270.1, 326, 379.1, 434.4, 488.3, 542.4, 598.4, 650),
                    6,
                    140,
                    313,
                ),
                "NA",
                "North America",
            ),
            (
                _TableSpec(
                    90,
                    "Gasoline-ethanol blends North America",
                    (28.3, 159.4, 214.7, 270.1, 326, 379.1, 434.4, 488.3, 542.4, 598.4, 650),
                    6,
                    325,
                    495,
                ),
                "NA",
                "North America",
            ),
        )
        for spec, geography_code, geography_name in blend_specs:
            for values in cells(spec):
                name = self._clean(values[0])
                ttw = self._number(values[5])
                wtw = self._number(values[6])
                if not name or ttw is None or wtw is None:
                    continue
                rows.append(
                    GlecFuelRow(
                        geography_code=geography_code,
                        geography_name=geography_name,
                        energy_carrier=name,
                        ttw_g_co2e_per_mj=ttw,
                        wtw_g_co2e_per_mj=wtw,
                        source_page=spec.page,
                        source_table=spec.name,
                    )
                )
        return self._unique(
            rows,
            lambda row: (
                row.geography_code,
                row.energy_carrier,
                row.application,
                row.ttw_g_co2e_per_mj,
                row.wtw_g_co2e_per_mj,
            ),
        )

    def _parse_intensities(self, cells: Any) -> list[GlecIntensityRow]:
        rows: list[GlecIntensityRow] = []
        rows.extend(self._air_intensities(cells))
        rows.extend(self._inland_intensities(cells))
        rows.extend(self._hub_intensities(cells))
        rows.extend(self._rail_intensities(cells))
        rows.extend(self._road_intensities(cells))
        rows.extend(self._sea_intensities(cells))
        rows.extend(self._container_intensities(cells))
        return self._unique(
            rows,
            lambda row: (
                row.source_table,
                row.category,
                row.detail,
                row.fuel,
                row.wtw_value,
            ),
        )

    def _air_intensities(self, cells: Any) -> list[GlecIntensityRow]:
        spec = _TableSpec(
            94,
            "Module 2 Table 1 - Air transport",
            (427.6, 501.3, 592.7, 666.3, 740.1, 811),
            4,
            400,
            523,
        )
        result: list[GlecIntensityRow] = []
        category = ""
        for values in cells(spec):
            category = self._clean(values[0]) or category
            detail = self._clean(values[1])
            wtt, ttw, wtw = (self._number(values[index]) for index in (2, 3, 4))
            if not category or not detail or wtw is None:
                continue
            result.append(
                self._intensity(
                    "air",
                    "GLOBAL",
                    "Global",
                    category,
                    detail,
                    None,
                    "tkm",
                    wtw,
                    wtt,
                    ttw,
                    "gCO2e/tkm",
                    spec,
                )
            )
        return result

    def _inland_intensities(self, cells: Any) -> list[GlecIntensityRow]:
        spec = _TableSpec(
            95,
            "Module 2 Table 2 - Inland waterways",
            (425.7, 524.7, 576.1, 620.9, 671.8, 722.8, 754, 785.2, 811),
            7,
            235,
            529,
        )
        result: list[GlecIntensityRow] = []
        for values in cells(spec):
            category = self._suffix_from(
                values[0],
                (
                    "Motor vessels",
                    "Coupled convoys",
                    "Pushed convoy",
                    "Tanker vessels",
                    "Container vessels",
                ),
            )
            wtt, ttw, wtw = (self._number(values[index]) for index in (5, 6, 7))
            if not category or wtw is None:
                continue
            result.append(
                self._intensity(
                    "inland-waterway",
                    "GLOBAL",
                    "Global",
                    category,
                    None,
                    self._clean(values[2]),
                    "tkm",
                    wtw,
                    wtt,
                    ttw,
                    "gCO2e/tkm",
                    spec,
                    {
                        "load_basis": self._clean(values[1]),
                        "fuel_intensity_kg_per_tkm": self._clean(values[3]),
                        "fuel_intensity_l_per_tkm": self._clean(values[4]),
                    },
                )
            )
        return result

    def _hub_intensities(self, cells: Any) -> list[GlecIntensityRow]:
        spec = _TableSpec(
            96,
            "Module 2 Table 3 - Logistics hubs",
            (425.7, 514.8, 564.1, 613.5, 668.3, 717.6, 767.1, 811),
            1,
            120,
            262,
        )
        result: list[GlecIntensityRow] = []
        for values in cells(spec):
            label = self._clean(values[0])
            if not label:
                continue
            activity_unit = "container" if "container" in label.casefold() else "t"
            for condition, value_col, sample_col in (
                ("ambient", 1, 2),
                ("temperature-controlled", 3, 4),
                ("mixed", 5, 6),
            ):
                value = self._number(values[value_col])
                if value is None:
                    continue
                result.append(
                    self._intensity(
                        "hub",
                        "GLOBAL",
                        "Global",
                        label,
                        condition,
                        None,
                        activity_unit,
                        value,
                        None,
                        None,
                        f"kgCO2e/{activity_unit}",
                        spec,
                        {"sample_size": self._clean(values[sample_col])},
                    )
                )
        return result

    def _rail_intensities(self, cells: Any) -> list[GlecIntensityRow]:
        specs = (
            (
                _TableSpec(
                    97,
                    "Module 2 Table 4 - European rail diesel",
                    (425.7, 514.8, 564.1, 614.1, 663.5, 713.8, 747.2, 780.5, 811),
                    7,
                    225,
                    401,
                ),
                "diesel",
                (5, 6, 7),
            ),
            (
                _TableSpec(
                    98,
                    "Module 2 Table 5 - European rail electric",
                    (227.5, 316.6, 365.9, 415.9, 465.3, 515, 565),
                    5,
                    225,
                    401,
                ),
                "electricity",
                (3, 4, 5),
            ),
        )
        result: list[GlecIntensityRow] = []
        for spec, fuel, indexes in specs:
            for values in cells(spec):
                category = self._suffix_from(
                    values[0],
                    (
                        "Average/mixed",
                        "Container",
                        "Cars",
                        "Chemicals",
                        "Coal & Steel",
                        "Building Materials",
                        "Manufactured Products",
                        "Cereals",
                        "Truck + trailer",
                        "Trailer only",
                    ),
                )
                wtt, ttw, wtw = (self._number(values[index]) for index in indexes)
                if not category or wtw is None:
                    continue
                result.append(
                    self._intensity(
                        "rail",
                        "EU",
                        "Europe",
                        category,
                        None,
                        fuel,
                        "tkm",
                        wtw,
                        wtt,
                        ttw,
                        "gCO2e/tkm",
                        spec,
                        {
                            "load_factor": self._clean(values[1]),
                            "empty_running": self._clean(values[2]),
                        },
                    )
                )
        return result

    def _road_intensities(self, cells: Any) -> list[GlecIntensityRow]:
        result: list[GlecIntensityRow] = []
        simple = _TableSpec(
            99,
            "Module 2 Table 6 - North American road",
            (425.9, 515, 564.4, 614.4, 663.7, 713.4, 763),
            5,
            205,
            450,
        )
        for values in cells(simple):
            category = self._clean(values[0])
            wtt, ttw, wtw = (self._number(values[index]) for index in (3, 4, 5))
            if category and wtw is not None:
                result.append(
                    self._intensity(
                        "road",
                        "NA",
                        "North America",
                        category,
                        None,
                        None,
                        "tkm",
                        wtw,
                        wtt,
                        ttw,
                        "gCO2e/tkm",
                        simple,
                        {
                            "fuel_intensity_kg_per_tkm": self._clean(values[1]),
                            "fuel_intensity_l_per_tkm": self._clean(values[2]),
                        },
                    )
                )

        van = _TableSpec(
            100,
            "Module 2 Table 7 - Europe and South America road",
            (336.5, 385.5, 435.2, 484.3, 533.5, 582.7, 632, 681.8, 731),
            7,
            210,
            282,
        )
        for values in cells(van):
            wtt, ttw, wtw = (self._number(values[index]) for index in (5, 6, 7))
            if wtw is not None:
                result.append(
                    self._intensity(
                        "road",
                        "EU_SA",
                        "Europe and South America",
                        "Van < 3.5 t",
                        None,
                        self._clean(values[2]),
                        "tkm",
                        wtw,
                        wtt,
                        ttw,
                        "gCO2e/tkm",
                        van,
                        {
                            "load_factor": self._clean(values[0]),
                            "empty_running": self._clean(values[1]),
                        },
                    )
                )

        road_specs = (
            (
                _TableSpec(
                    101,
                    "Module 2 Table 8 - Europe and South America road",
                    (28.5, 119.2, 188.3, 246.8, 305, 371.8, 421, 471, 520.3, 570.1, 620),
                    9,
                    95,
                    566,
                ),
                "EU_SA",
                "Europe and South America",
            ),
            (
                _TableSpec(
                    102,
                    "Module 2 Table 9 - Europe and South America road",
                    (28.5, 119.2, 188.3, 246.8, 305, 371.8, 421, 471, 520.3, 570.1, 620),
                    9,
                    90,
                    378,
                ),
                "EU_SA",
                "Europe and South America",
            ),
            (
                _TableSpec(
                    103,
                    "Module 2 Table 12 - China road",
                    (227.4, 318.2, 387.2, 445.8, 503.9, 570.8, 620, 669.9, 719.3, 769, 811),
                    9,
                    180,
                    555,
                ),
                "CN",
                "China",
            ),
            (
                _TableSpec(
                    104,
                    "Module 2 Table 12 - China road",
                    (28.3, 119.1, 188.2, 246.7, 304.8, 371.7, 420.9, 470.9, 520.2, 569.9, 620),
                    9,
                    130,
                    558,
                ),
                "CN",
                "China",
            ),
            (
                _TableSpec(
                    105,
                    "Module 2 Table 12 - China road",
                    (28.3, 119.1, 188.2, 246.7, 304.8, 371.7, 420.9, 470.9, 520.2, 569.9, 620),
                    9,
                    130,
                    558,
                ),
                "CN",
                "China",
            ),
            (
                _TableSpec(
                    106,
                    "Module 2 Table 13 - India road",
                    (28.3, 123.3, 188.2, 246.7, 304.8, 371.7, 420.9, 470.9, 520.2, 569.9, 620),
                    9,
                    140,
                    512,
                ),
                "IN",
                "India",
            ),
        )
        for spec, geography_code, geography_name in road_specs:
            extracted = cells(spec)
            vehicle = ""
            load = ""
            fuel = ""
            for values in extracted:
                vehicle_fragment = self._suffix_from(
                    values[0],
                    (
                        "Van",
                        "Rigid",
                        "Artic",
                        "Dump",
                        "Truck",
                        "Small Commercial",
                        "Medium Commercial",
                        "Heavy Commercial",
                        "Tractor Trailer",
                    ),
                )
                if vehicle_fragment and not vehicle_fragment.startswith(("|", "MT |")):
                    vehicle = vehicle_fragment
                elif vehicle_fragment:
                    vehicle = " ".join(part for part in (vehicle, vehicle_fragment) if part)
                load = (
                    self._suffix_from(
                        values[1], ("Light", "Average/mixed", "Heavy", "Container", "Average")
                    )
                    or load
                )
                fuel = (
                    self._suffix_from(
                        values[4],
                        (
                            "Diesel",
                            "Petrol",
                            "CNG",
                            "Bio-LNG",
                            "LNG",
                            "Electricity",
                            "Hydrogen",
                        ),
                    )
                    or fuel
                )
                wtt, ttw, wtw = (self._number(values[index]) for index in (7, 8, 9))
                if not vehicle or wtw is None:
                    continue
                result.append(
                    self._intensity(
                        "road",
                        geography_code,
                        geography_name,
                        vehicle,
                        load or None,
                        fuel or None,
                        "tkm",
                        wtw,
                        wtt,
                        ttw,
                        "gCO2e/tkm",
                        spec,
                        {
                            "load_factor": self._clean(values[2]),
                            "empty_running": self._clean(values[3]),
                            "fuel_intensity_kg_per_tkm": self._clean(values[5]),
                            "fuel_intensity_l_per_tkm": self._clean(values[6]),
                        },
                    )
                )
        return result

    def _sea_intensities(self, cells: Any) -> list[GlecIntensityRow]:
        specs = (
            _TableSpec(
                107,
                "Module 2 Table 14 - Non-container vessels",
                (427, 502.3, 575.8, 621, 665.7, 702.5, 739.5, 776.6, 811),
                7,
                220,
                528,
            ),
            _TableSpec(
                108,
                "Module 2 Table 15 - Non-container vessels",
                (29.4, 103.5, 177.4, 222.6, 268.3, 304.2, 341, 378.4, 410),
                7,
                150,
                566,
            ),
            _TableSpec(
                108,
                "Module 2 Table 15 - Non-container vessels",
                (427.5, 503.9, 576.7, 621.4, 667.4, 703.3, 740.2, 777.5, 811),
                7,
                150,
                566,
            ),
            _TableSpec(
                109,
                "Module 2 Table 16 - Non-container vessels",
                (29.2, 104, 177.4, 222.9, 267.7, 304.4, 341.3, 378.4, 410),
                7,
                150,
                567,
            ),
            _TableSpec(
                109,
                "Module 2 Table 16 - Non-container vessels",
                (428.9, 503.9, 577.1, 621.6, 666.7, 704.1, 741, 778.1, 811),
                7,
                150,
                567,
            ),
            _TableSpec(
                110,
                "Module 2 Table 17 - Non-container vessels",
                (27.6, 103.5, 176.6, 221.5, 267.7, 304.4, 341.3, 378.4, 410),
                7,
                150,
                515,
            ),
        )
        result: list[GlecIntensityRow] = []
        category_markers = (
            "Bulk carrier",
            "Chemical tanker",
            "General cargo",
            "Liquefied gas tanker",
            "Oil tanker",
            "Other liquids tankers",
            "Ferry-RoPax",
            "Refrigerated bulk",
            "Ro-Ro",
            "Vehicle",
        )
        for spec in specs:
            category = ""
            size = ""
            unit = ""
            for values in cells(spec):
                category = (
                    self._suffix_from(values[0], category_markers).replace(" (Continued)", "")
                    or category
                )
                size = (
                    re.sub(r"^(?:and\s+)?size\s+", "", self._clean(values[1]), flags=re.IGNORECASE)
                    or size
                )
                unit = self._clean(values[2]) or unit
                fuel = re.sub(r"^Fuel\s+", "", self._clean(values[3]), flags=re.IGNORECASE)
                wtt, ttw, base_wtw, end_user_wtw = (
                    self._number(values[index]) for index in (4, 5, 6, 7)
                )
                if not category or not fuel or end_user_wtw is None:
                    continue
                result.append(
                    self._intensity(
                        "sea",
                        "GLOBAL",
                        "Global",
                        category,
                        size or None,
                        fuel,
                        "tkm",
                        end_user_wtw,
                        wtt,
                        ttw,
                        "gCO2e/tkm",
                        spec,
                        {
                            "vessel_size_unit": unit,
                            "base_wtw_g_co2e_per_tkm": str(base_wtw)
                            if base_wtw is not None
                            else "",
                            "distance_adjustment": "15%",
                        },
                    )
                )
        return result

    def _container_intensities(self, cells: Any) -> list[GlecIntensityRow]:
        specs = (
            _TableSpec(
                111,
                "Module 2 Table 18 - Container vessels",
                (28.3, 103.8, 136.1, 204.5, 273, 341.7, 410),
                5,
                150,
                567,
            ),
            _TableSpec(
                111,
                "Module 2 Table 18 - Container vessels",
                (425.9, 501.4, 533.6, 602.1, 670.5, 739.3, 811),
                5,
                150,
                567,
            ),
            _TableSpec(
                112,
                "Module 2 Table 19 - Container vessels",
                (28.3, 103.8, 136.1, 204.5, 273, 341.7, 410),
                5,
                150,
                440,
            ),
            _TableSpec(
                112,
                "Module 2 Table 19 - Container vessels",
                (425.9, 501.4, 533.6, 602.1, 670.5, 739.3, 811),
                5,
                150,
                440,
            ),
        )
        result: list[GlecIntensityRow] = []
        for spec in specs:
            extracted = [row for row in cells(spec) if self._clean(row[1]) in {"Dry", "Reefer"}]
            index = 0
            while index < len(extracted):
                dry = extracted[index]
                reefer = extracted[index + 1] if index + 1 < len(extracted) else None
                pair = [dry] + (
                    [reefer] if reefer is not None and self._clean(reefer[1]) == "Reefer" else []
                )
                lane = " ".join(self._clean(row[0]) for row in pair if self._clean(row[0]))
                for values in pair:
                    aggregate, wtt, ttw, wtw = (
                        self._number(values[column]) for column in (2, 3, 4, 5)
                    )
                    if lane and wtw is not None:
                        result.append(
                            self._intensity(
                                "sea-container",
                                "GLOBAL",
                                "Global",
                                lane,
                                self._clean(values[1]),
                                None,
                                "TEU-km",
                                wtw,
                                wtt,
                                ttw,
                                "gCO2e/TEU-km",
                                spec,
                                {
                                    "aggregate_average_g_co2e_per_teu_km": str(aggregate)
                                    if aggregate is not None
                                    else ""
                                },
                                aggregate,
                            )
                        )
                index += len(pair)
        return result

    def _parse_refrigerants(self, cells: Any) -> list[GlecRefrigerantRow]:
        specs = (
            _TableSpec(
                114,
                "Module 3 Table 2 - Refrigerants",
                (28.3, 104, 220.3, 335.3, 426.6),
                3,
                140,
                566,
            ),
            _TableSpec(
                114,
                "Module 3 Table 2 - Refrigerants",
                (426.6, 502.3, 618.5, 733.5, 811),
                3,
                140,
                507,
            ),
        )
        result: list[GlecRefrigerantRow] = []
        for spec in specs:
            for values in cells(spec):
                name = self._clean(values[0])
                if not name.startswith(("R-", "ISCEON", "FX 100")):
                    continue
                result.append(
                    GlecRefrigerantRow(
                        refrigerant=name,
                        chemical_formula=self._clean(values[1]) or None,
                        alternative_name=self._clean(values[2]) or None,
                        gwp100_ar6=self._number(values[3]),
                    )
                )
        return self._unique(result, lambda row: row.refrigerant.casefold())

    def _parse_parameters(self, cells: Any) -> list[GlecParameterRow]:
        spec = _TableSpec(
            113,
            "Module 3 Table 1 - Refrigerant loss defaults",
            (432.7, 537, 639.8, 811),
            1,
            320,
            389,
        )
        result: list[GlecParameterRow] = []
        equipment = ("mobile air conditioning units", "temperature-controlled mobile freight units")
        for values in cells(spec):
            name = self._clean(values[0])
            for column, equipment_type in ((1, equipment[0]), (2, equipment[1])):
                value = self._number(values[column])
                if not name or value is None:
                    continue
                unit = "%" if "rate" in name.casefold() else "kg"
                if unit == "%":
                    value /= Decimal(100)
                    unit = "fraction"
                result.append(
                    GlecParameterRow(
                        name=name, equipment_type=equipment_type, value=value, unit=unit
                    )
                )
        return result

    @classmethod
    def _intensity(
        cls,
        mode: str,
        geography_code: str,
        geography_name: str,
        category: str,
        detail: str | None,
        fuel: str | None,
        activity_unit: str,
        wtw: Decimal,
        wtt: Decimal | None,
        ttw: Decimal | None,
        source_unit: str,
        spec: _TableSpec,
        attributes: dict[str, str] | None = None,
        aggregate: Decimal | None = None,
    ) -> GlecIntensityRow:
        return GlecIntensityRow(
            mode=mode,
            geography_code=geography_code,
            geography_name=geography_name,
            category=cls._clean(category),
            detail=cls._clean(detail) or None,
            fuel=cls._clean(fuel) or None,
            activity_unit=activity_unit,
            wtw_value=wtw,
            wtt_value=wtt,
            ttw_value=ttw,
            aggregate_value=aggregate,
            source_unit=source_unit,
            source_page=spec.page,
            source_table=spec.name,
            attributes={key: value for key, value in (attributes or {}).items() if value},
        )

    @staticmethod
    def _center(word: dict[str, Any]) -> float:
        return (float(word["x0"]) + float(word["x1"])) / 2

    @staticmethod
    def _is_number_or_dash(value: str) -> bool:
        return value == "-" or GlecParser._number(value) is not None

    @staticmethod
    def _number(value: str) -> Decimal | None:
        matches = re.findall(r"-?\d+(?:,\d{3})*(?:\.\d+)?", value)
        if not matches:
            return None
        try:
            return Decimal(matches[-1].replace(",", ""))
        except InvalidOperation:
            return None

    @staticmethod
    def _clean(value: str | None) -> str:
        return " ".join((value or "").replace(chr(0x2013), "-").replace(chr(0x2012), "-").split())

    @classmethod
    def _suffix_from(cls, value: str, markers: tuple[str, ...]) -> str:
        cleaned = cls._clean(value)
        positions = [cleaned.find(marker) for marker in markers if marker in cleaned]
        return cleaned[min(positions) :] if positions else cleaned

    @staticmethod
    def _unique(rows: Iterable[Any], key: Any) -> list[Any]:
        result: list[Any] = []
        seen: set[Any] = set()
        for row in rows:
            identity = key(row)
            if identity in seen:
                continue
            seen.add(identity)
            result.append(row)
        return result
