from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import ClassVar
from xml.etree import ElementTree

import pdfplumber
from pydantic import BaseModel, ConfigDict

from atlas.domain.models import ParsedRecord
from atlas.ingestion.errors import PermanentIngestionError


@dataclass(frozen=True)
class ReportSpec:
    pdf_name: str
    product_keys: tuple[str, ...]


@dataclass(frozen=True)
class PackageSpec:
    key: str
    filename: str
    family: str
    reference_year: int
    valid_from: date
    valid_to: date
    reports: tuple[ReportSpec, ...]


class PlasticsEuropeRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    process_uuid: str
    process_name: str
    product_key: str
    product_name: str
    family: str
    reference_year: int
    valid_from: date
    valid_to: date
    reference_amount: Decimal
    reference_unit: str
    gwp100_kgco2e: Decimal
    package_key: str
    package_filename: str
    package_url: str
    package_sha256: str
    xml_member: str
    pdf_member: str
    source_row: int

    def as_parsed_record(self) -> ParsedRecord:
        return ParsedRecord(
            data=self.model_dump(mode="json"),
            source_row=self.source_row,
            source_sheet=self.xml_member,
            source_table=self.pdf_member,
        )


class PlasticsEuropeParser:
    packages: ClassVar[tuple[PackageSpec, ...]] = (
        PackageSpec(
            key="pe_and_pp",
            filename="PE-and-PP.zip",
            family="Polyolefin resins",
            reference_year=2024,
            valid_from=date(2024, 1, 1),
            valid_to=date(2029, 12, 31),
            reports=(
                ReportSpec(
                    "Eco-profile PE PP 2026.pdf",
                    ("HDPE", "LDPE", "LLDPE", "PP"),
                ),
            ),
        ),
        PackageSpec(
            key="cvm_and_pvc",
            filename="CVM-and-PVC.zip",
            family="Vinyl chloride and PVC resins",
            reference_year=2023,
            valid_from=date(2023, 1, 1),
            valid_to=date(2028, 12, 31),
            reports=(
                ReportSpec("Eco-profile PVC 2026.pdf", ("VCM", "SPVC", "EPVC")),
            ),
        ),
        PackageSpec(
            key="steam_cracker",
            filename="Steam-Cracker.zip",
            family="Steam cracker products and aromatics",
            reference_year=2023,
            valid_from=date(2023, 1, 1),
            valid_to=date(2028, 12, 31),
            reports=(
                ReportSpec(
                    "Eco-profile SC 2026.pdf",
                    (
                        "Ethylene",
                        "Propylene",
                        "Butadiene",
                        "PyGas",
                        "H2",
                        "EO",
                        "MEG",
                        "DEG",
                        "TEG",
                    ),
                ),
                ReportSpec(
                    "Eco-profile SC Aromatics 2026.pdf",
                    ("Benzene", "Toluene", "o-Xylene", "p-Xylene", "Mixed Xylenes"),
                ),
            ),
        ),
        PackageSpec(
            key="refinery",
            filename="Refinery.zip",
            family="Refinery feedstocks",
            reference_year=2023,
            valid_from=date(2023, 1, 1),
            valid_to=date(2028, 12, 31),
            reports=(
                ReportSpec(
                    "Eco-profile Refinery 2026.pdf",
                    (
                        "Naphtha",
                        "Atmospheric Gas Oil",
                        "Propylene from FCC",
                        "Reformate",
                        "Propane+Butane",
                        "Diesel",
                        "Petrol",
                    ),
                ),
            ),
        ),
    )
    product_names: ClassVar[dict[str, str]] = {
        "HDPE": "High-density polyethylene resin (HDPE)",
        "LDPE": "Low-density polyethylene resin (LDPE)",
        "LLDPE": "Linear low-density polyethylene resin (LLDPE)",
        "PP": "Polypropylene resin (PP)",
        "VCM": "Vinyl chloride monomer (VCM)",
        "SPVC": "Suspension polyvinyl chloride resin (S-PVC)",
        "EPVC": "Emulsion polyvinyl chloride resin (E-PVC)",
        "Ethylene": "Ethylene",
        "Propylene": "Propylene",
        "Butadiene": "Butadiene",
        "PyGas": "Pyrolysis gasoline",
        "H2": "Hydrogen",
        "EO": "Ethylene oxide",
        "MEG": "Monoethylene glycol",
        "DEG": "Diethylene glycol",
        "TEG": "Triethylene glycol",
        "Benzene": "Benzene",
        "Toluene": "Toluene",
        "o-Xylene": "o-Xylene",
        "p-Xylene": "p-Xylene",
        "Mixed Xylenes": "Mixed xylenes",
        "Naphtha": "Naphtha",
        "Atmospheric Gas Oil": "Atmospheric gas oil",
        "Propylene from FCC": "Propylene from fluid catalytic cracking",
        "Reformate": "Reformate",
        "Propane+Butane": "Propane/butane mix",
        "Diesel": "Diesel",
        "Petrol": "Petrol",
    }

    def __init__(
        self,
        *,
        packages: tuple[PackageSpec, ...] | None = None,
        pdf_text_extractor: Callable[[bytes], tuple[str, ...]] | None = None,
    ) -> None:
        self.package_specs = packages or self.packages
        self.pdf_text_extractor = pdf_text_extractor or self._pdf_pages
        self.metrics: dict[str, int] = {}

    def parse(self, path: Path) -> tuple[PlasticsEuropeRow, ...]:
        try:
            bundle = zipfile.ZipFile(path)
        except zipfile.BadZipFile as error:
            raise PermanentIngestionError(
                "Plastics Europe acquisition bundle is not a valid ZIP"
            ) from error
        with bundle:
            try:
                manifest = json.loads(bundle.read("bundle-manifest.json"))
            except (KeyError, json.JSONDecodeError) as error:
                raise PermanentIngestionError(
                    "Plastics Europe bundle manifest is missing or invalid"
                ) from error
            package_metadata = manifest.get("packages")
            if not isinstance(package_metadata, dict):
                raise PermanentIngestionError(
                    "Plastics Europe bundle package metadata is invalid"
                )
            rows: list[PlasticsEuropeRow] = []
            source_row = 0
            for spec in self.package_specs:
                member = f"packages/{spec.filename}"
                try:
                    content = bundle.read(member)
                except KeyError as error:
                    raise PermanentIngestionError(
                        f"Plastics Europe bundle has no {spec.filename}"
                    ) from error
                metadata = package_metadata.get(spec.key)
                if not isinstance(metadata, dict):
                    raise PermanentIngestionError(
                        f"Plastics Europe bundle has no metadata for {spec.key}"
                    )
                package_sha = hashlib.sha256(content).hexdigest()
                if metadata.get("sha256") != package_sha:
                    raise PermanentIngestionError(
                        f"Plastics Europe {spec.filename} checksum mismatch"
                    )
                package_rows = self._package_rows(
                    spec,
                    content,
                    package_url=str(metadata.get("url") or ""),
                    package_sha=package_sha,
                    source_row_start=source_row,
                )
                rows.extend(package_rows)
                source_row += len(package_rows)
        expected = sum(
            len(report.product_keys)
            for package in self.package_specs
            for report in package.reports
        )
        if len(rows) != expected:
            raise PermanentIngestionError(
                f"Plastics Europe expected {expected} climate results; found {len(rows)}"
            )
        family_counts: dict[str, int] = {}
        for row in rows:
            family_counts[row.family] = family_counts.get(row.family, 0) + 1
        self.metrics = {
            "input_packages": len(self.package_specs),
            "input_xml_processes": len(rows),
            "parsed_rows": len(rows),
            **{
                f"family_{self._metric_key(family)}_rows": count
                for family, count in family_counts.items()
            },
        }
        return tuple(rows)

    def _package_rows(
        self,
        spec: PackageSpec,
        content: bytes,
        *,
        package_url: str,
        package_sha: str,
        source_row_start: int,
    ) -> list[PlasticsEuropeRow]:
        try:
            package = zipfile.ZipFile(io.BytesIO(content))
        except zipfile.BadZipFile as error:
            raise PermanentIngestionError(
                f"Plastics Europe {spec.filename} is not a valid ZIP"
            ) from error
        with package:
            processes = self._processes(package, spec)
            expected_keys = {
                product_key for report in spec.reports for product_key in report.product_keys
            }
            if set(processes) != expected_keys:
                raise PermanentIngestionError(
                    f"Plastics Europe {spec.filename} process set changed: "
                    f"expected {sorted(expected_keys)}, found {sorted(processes)}"
                )
            values: dict[str, tuple[Decimal, str]] = {}
            for report in spec.reports:
                pdf_member = self._member_ending(package, report.pdf_name)
                pages = self.pdf_text_extractor(package.read(pdf_member))
                climate_values = self._climate_values(
                    pages, expected_count=len(report.product_keys), pdf_name=report.pdf_name
                )
                for product_key, value in zip(
                    report.product_keys, climate_values, strict=True
                ):
                    values[product_key] = (value, pdf_member)
            rows: list[PlasticsEuropeRow] = []
            ordered_keys = [
                product_key for report in spec.reports for product_key in report.product_keys
            ]
            for offset, product_key in enumerate(ordered_keys, start=1):
                process = processes[product_key]
                value, pdf_member = values[product_key]
                rows.append(
                    PlasticsEuropeRow(
                        process_uuid=process[0],
                        process_name=process[1],
                        product_key=product_key,
                        product_name=self.product_names.get(product_key, product_key),
                        family=spec.family,
                        reference_year=spec.reference_year,
                        valid_from=spec.valid_from,
                        valid_to=spec.valid_to,
                        reference_amount=process[2],
                        reference_unit=process[3],
                        gwp100_kgco2e=value,
                        package_key=spec.key,
                        package_filename=spec.filename,
                        package_url=package_url,
                        package_sha256=package_sha,
                        xml_member=process[4],
                        pdf_member=pdf_member,
                        source_row=source_row_start + offset,
                    )
                )
        return rows

    @classmethod
    def _processes(
        cls, package: zipfile.ZipFile, spec: PackageSpec
    ) -> dict[str, tuple[str, str, Decimal, str, str]]:
        processes: dict[str, tuple[str, str, Decimal, str, str]] = {}
        for member in sorted(name for name in package.namelist() if name.endswith(".xml")):
            try:
                root = ElementTree.fromstring(package.read(member))
            except ElementTree.ParseError as error:
                raise PermanentIngestionError(
                    f"Plastics Europe {member} is invalid ILCD XML"
                ) from error
            process_uuid = cls._required_text(root, "UUID", member)
            process_name = cls._required_text(root, "baseName", member)
            reference_id = cls._required_text(root, "referenceToReferenceFlow", member)
            reference_exchange = next(
                (
                    element
                    for element in root.iter()
                    if cls._local_name(element.tag) == "exchange"
                    and element.attrib.get("dataSetInternalID") == reference_id
                ),
                None,
            )
            if reference_exchange is None:
                raise PermanentIngestionError(
                    f"Plastics Europe {member} has no reference exchange"
                )
            amount_text = cls._required_text(reference_exchange, "meanAmount", member)
            try:
                amount = Decimal(amount_text)
            except InvalidOperation as error:
                raise PermanentIngestionError(
                    f"Plastics Europe {member} has invalid reference amount"
                ) from error
            unit = next(
                (
                    value
                    for key, value in reference_exchange.attrib.items()
                    if cls._local_name(key) == "unitName"
                ),
                "",
            )
            if amount != Decimal("1") or unit.lower() not in {"kg", "kilogram"}:
                raise PermanentIngestionError(
                    f"Plastics Europe {member} expected a 1 kg reference flow"
                )
            parts = process_name.split("--")
            if len(parts) < 3:
                raise PermanentIngestionError(
                    f"Plastics Europe {member} process name contract changed"
                )
            product_key = parts[-2].strip()
            if product_key in processes:
                raise PermanentIngestionError(
                    f"Plastics Europe {spec.filename} has duplicate {product_key}"
                )
            processes[product_key] = (process_uuid, process_name, amount, "kg", member)
        return processes

    @classmethod
    def _climate_values(
        cls, pages: tuple[str, ...], *, expected_count: int, pdf_name: str
    ) -> tuple[Decimal, ...]:
        lines = [
            line
            for page in pages
            if "LCIA Results" in page and "Climate change" in page
            for line in page.splitlines()
            if line.strip().startswith("Climate change")
        ]
        if len(lines) != 1:
            raise PermanentIngestionError(
                f"Plastics Europe {pdf_name} expected one LCIA climate summary row; "
                f"found {len(lines)}"
            )
        tokens = re.findall(r"[-+]?\d+(?:\.\d+)?(?:E[-+]?\d+)?", lines[0], re.IGNORECASE)
        if len(tokens) < expected_count:
            raise PermanentIngestionError(
                f"Plastics Europe {pdf_name} climate result count changed"
            )
        try:
            values = tuple(Decimal(token) for token in tokens[-expected_count:])
        except InvalidOperation as error:
            raise PermanentIngestionError(
                f"Plastics Europe {pdf_name} has invalid climate values"
            ) from error
        if any(not value.is_finite() or value < 0 for value in values):
            raise PermanentIngestionError(
                f"Plastics Europe {pdf_name} has invalid climate values"
            )
        return values

    @staticmethod
    def _pdf_pages(content: bytes) -> tuple[str, ...]:
        try:
            with pdfplumber.open(io.BytesIO(content)) as document:
                return tuple(page.extract_text() or "" for page in document.pages)
        except Exception as error:
            raise PermanentIngestionError(
                "Plastics Europe Eco-profile PDF could not be parsed"
            ) from error

    @staticmethod
    def _member_ending(package: zipfile.ZipFile, suffix: str) -> str:
        matches = [name for name in package.namelist() if name.endswith(suffix)]
        if len(matches) != 1:
            raise PermanentIngestionError(
                f"Plastics Europe expected one {suffix}; found {len(matches)}"
            )
        return matches[0]

    @classmethod
    def _required_text(cls, root: ElementTree.Element, name: str, member: str) -> str:
        value = next(
            (
                " ".join((element.text or "").split())
                for element in root.iter()
                if cls._local_name(element.tag) == name and (element.text or "").strip()
            ),
            "",
        )
        if not value:
            raise PermanentIngestionError(f"Plastics Europe {member} has no {name}")
        return value

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    @staticmethod
    def _metric_key(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
