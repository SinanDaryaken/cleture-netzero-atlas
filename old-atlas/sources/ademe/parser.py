from __future__ import annotations

import csv
import io
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from atlas.domain.models import ParsedRecord
from atlas.ingestion.errors import PermanentIngestionError

EXPECTED_HEADERS = (
    "Type Ligne",
    "Identifiant de l'élément",
    "Structure",
    "Type de l'élément",
    "Statut de l'élément",
    "Nom base français",
    "Nom base anglais",
    "Nom base espagnol",
    "Nom attribut français",
    "Nom attribut anglais",
    "Nom attribut espagnol",
    "Nom frontière français",
    "Nom frontière anglais",
    "Nom frontière espagnol",
    "Code de la catégorie",
    "Tags français",
    "Tags anglais",
    "Tags espagnol",
    "Unité français",
    "Unité anglais",
    "Unité espagnol",
    "Contributeur",
    "Autres Contributeurs",
    "Programme",
    "Url du programme",
    "Source",
    "Localisation géographique",
    "Sous-localisation géographique français",
    "Sous-localisation géographique anglais",
    "Sous-localisation géographique espagnol",
    "Date de création",
    "Date de modification",
    "Période de validité",
    "Incertitude",
    "Réglementations",
    "Transparence",
    "Qualité",
    "Qualité TeR",
    "Qualité GR",
    "Qualité TiR",
    "Qualité C",
    "Qualité P",
    "Qualité M",
    "Commentaire français",
    "Commentaire anglais",
    "Commentaire espagnol",
    "Type poste",
    "Nom poste français",
    "Nom poste anglais",
    "Nom poste espagnol",
    "Total poste non décomposé",
    "CO2f",
    "CH4f",
    "CH4b",
    "N2O",
    "Code gaz supplémentaire 1",
    "Valeur gaz supplémentaire 1",
    "Code gaz supplémentaire 2",
    "Valeur gaz supplémentaire 2",
    "Code gaz supplémentaire 3",
    "Valeur gaz supplémentaire 3",
    "Code gaz supplémentaire 4",
    "Valeur gaz supplémentaire 4",
    "Code gaz supplémentaire 5",
    "Valeur gaz supplémentaire 5",
    "Autres GES",
    "CO2b",
)


class AdemeRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    line_type: str
    element_id: str
    structure: str
    element_type: str
    status: str
    name_fr: str | None = None
    name_en: str | None = None
    attribute_fr: str | None = None
    attribute_en: str | None = None
    boundary_fr: str | None = None
    boundary_en: str | None = None
    category_path: str | None = None
    tags_fr: str | None = None
    unit_fr: str | None = None
    unit_en: str | None = None
    contributor: str | None = None
    other_contributors: str | None = None
    program: str | None = None
    program_url: str | None = None
    source: str | None = None
    geographic_location: str | None = None
    sub_location_fr: str | None = None
    sub_location_en: str | None = None
    created_on: str | None = None
    modified_on: str | None = None
    validity_period: str | None = None
    uncertainty: Decimal | None = None
    transparency: Decimal | None = None
    quality: Decimal | None = None
    comment_fr: str | None = None
    comment_en: str | None = None
    post_type: str | None = None
    post_name_fr: str | None = None
    post_name_en: str | None = None
    total: Decimal | None = None
    co2_fossil: Decimal | None = None
    ch4_fossil: Decimal | None = None
    ch4_biogenic: Decimal | None = None
    n2o: Decimal | None = None
    other_ghg: Decimal | None = None
    co2_biogenic: Decimal | None = None
    additional_gases: dict[str, Decimal] = Field(default_factory=dict)
    source_row: int

    @property
    def is_valid_factor_element(self) -> bool:
        return (
            self.line_type == "Elément"
            and self.element_type == "Facteur d'émission"
            and self.status in {"Valide générique", "Valide spécifique"}
        )

    @property
    def is_factor_post(self) -> bool:
        return (
            self.line_type == "Poste"
            and self.element_type == "Facteur d'émission"
            and self.status in {"Valide générique", "Valide spécifique"}
        )

    def as_parsed_record(self) -> ParsedRecord:
        return ParsedRecord(
            data=self.model_dump(mode="json"),
            source_row=self.source_row,
            source_table="Base Carbone",
        )


class AdemeParser:
    """Parse the versioned, semicolon-delimited Base Carbone export."""

    def __init__(self) -> None:
        self.metrics: dict[str, int] = {}

    def parse(self, path: Path) -> tuple[AdemeRow, ...]:
        content = self._read_text(path)
        reader = csv.DictReader(io.StringIO(content, newline=""), delimiter=";")
        headers = tuple(reader.fieldnames or ())
        if headers != EXPECTED_HEADERS:
            raise PermanentIngestionError(
                "ADEME Base Carbone schema changed; parser version must be updated"
            )

        rows: list[AdemeRow] = []
        for source_row, payload in enumerate(reader, start=2):
            if None in payload:
                raise PermanentIngestionError(
                    f"ADEME Base Carbone has excess columns at record {source_row}"
                )
            if not any(self._text(value) for value in payload.values()):
                continue
            rows.append(self._row(payload, source_row))
        if not rows:
            raise PermanentIngestionError("ADEME Base Carbone export contains no records")

        valid_ids = [row.element_id for row in rows if row.is_valid_factor_element]
        if len(valid_ids) != len(set(valid_ids)):
            raise PermanentIngestionError(
                "ADEME Base Carbone contains duplicate valid factor element ids"
            )
        self.metrics = {
            "exported_rows": len(rows),
            "valid_factor_elements": len(valid_ids),
            "valid_factor_posts": sum(row.is_factor_post for row in rows),
            "archived_rows": sum(row.status == "Archivé" for row in rows),
            "source_data_rows": sum(row.element_type == "Données source" for row in rows),
        }
        return tuple(rows)

    def _row(self, payload: dict[str | None, str | None], source_row: int) -> AdemeRow:
        element_id = self._required(payload, "Identifiant de l'élément", source_row)
        additional_gases: dict[str, Decimal] = {}
        for index in range(1, 6):
            code = self._text(payload.get(f"Code gaz supplémentaire {index}"))
            value = self._decimal(payload.get(f"Valeur gaz supplémentaire {index}"), source_row)
            if code is not None and value is not None:
                additional_gases[code] = value
        return AdemeRow(
            line_type=self._required(payload, "Type Ligne", source_row),
            element_id=element_id,
            structure=self._required(payload, "Structure", source_row),
            element_type=self._required(payload, "Type de l'élément", source_row),
            status=self._required(payload, "Statut de l'élément", source_row),
            name_fr=self._text(payload.get("Nom base français")),
            name_en=self._text(payload.get("Nom base anglais")),
            attribute_fr=self._text(payload.get("Nom attribut français")),
            attribute_en=self._text(payload.get("Nom attribut anglais")),
            boundary_fr=self._text(payload.get("Nom frontière français")),
            boundary_en=self._text(payload.get("Nom frontière anglais")),
            category_path=self._text(payload.get("Code de la catégorie")),
            tags_fr=self._text(payload.get("Tags français")),
            unit_fr=self._text(payload.get("Unité français")),
            unit_en=self._text(payload.get("Unité anglais")),
            contributor=self._text(payload.get("Contributeur")),
            other_contributors=self._text(payload.get("Autres Contributeurs")),
            program=self._text(payload.get("Programme")),
            program_url=self._text(payload.get("Url du programme")),
            source=self._text(payload.get("Source")),
            geographic_location=self._text(payload.get("Localisation géographique")),
            sub_location_fr=self._text(payload.get("Sous-localisation géographique français")),
            sub_location_en=self._text(payload.get("Sous-localisation géographique anglais")),
            created_on=self._text(payload.get("Date de création")),
            modified_on=self._text(payload.get("Date de modification")),
            validity_period=self._text(payload.get("Période de validité")),
            uncertainty=self._decimal(payload.get("Incertitude"), source_row),
            transparency=self._decimal(payload.get("Transparence"), source_row),
            quality=self._decimal(payload.get("Qualité"), source_row),
            comment_fr=self._text(payload.get("Commentaire français")),
            comment_en=self._text(payload.get("Commentaire anglais")),
            post_type=self._text(payload.get("Type poste")),
            post_name_fr=self._text(payload.get("Nom poste français")),
            post_name_en=self._text(payload.get("Nom poste anglais")),
            total=self._decimal(payload.get("Total poste non décomposé"), source_row),
            co2_fossil=self._decimal(payload.get("CO2f"), source_row),
            ch4_fossil=self._decimal(payload.get("CH4f"), source_row),
            ch4_biogenic=self._decimal(payload.get("CH4b"), source_row),
            n2o=self._decimal(payload.get("N2O"), source_row),
            other_ghg=self._decimal(payload.get("Autres GES"), source_row),
            co2_biogenic=self._decimal(payload.get("CO2b"), source_row),
            additional_gases=additional_gases,
            source_row=source_row,
        )

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            return path.read_text(encoding="cp1252")

    @staticmethod
    def _text(value: object) -> str | None:
        if value is None:
            return None
        normalized = " ".join(str(value).split())
        # The official CP1252 export double-escapes 19 quoted Agribalyse labels.
        # Reverse only that explicit outer-quote shape; ordinary quotes are retained.
        if normalized.startswith('"""') and normalized.endswith('"""'):
            normalized = normalized[3:-3].replace('""""', '"')
        return normalized or None

    @classmethod
    def _required(cls, payload: dict[str | None, str | None], field: str, source_row: int) -> str:
        value = cls._text(payload.get(field))
        if value is None:
            raise PermanentIngestionError(
                f"ADEME Base Carbone {field} is missing at record {source_row}"
            )
        return value

    @staticmethod
    def _decimal(value: object, source_row: int) -> Decimal | None:
        if value is None or not str(value).strip():
            return None
        normalized = str(value).strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
        try:
            return Decimal(normalized)
        except InvalidOperation as error:
            raise PermanentIngestionError(
                f"invalid ADEME numeric value at record {source_row}: {value}"
            ) from error
