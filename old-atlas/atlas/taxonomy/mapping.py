from pathlib import Path

import yaml

from atlas.domain.enums import GeographyLevel
from atlas.domain.models import Geography
from atlas.ingestion.errors import PermanentIngestionError


class SourceMapping:
    def __init__(self, path: Path) -> None:
        with path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"mapping file must contain an object: {path}")
        self.version = str(payload["version"])
        self.categories: dict[str, str] = dict(payload["categories"])

    def taxonomy_code(self, level_1: str) -> str:
        try:
            return self.categories[level_1]
        except KeyError as error:
            raise PermanentIngestionError(f"unmapped DEFRA category: {level_1}") from error

    @staticmethod
    def defra_origin_geography() -> Geography:
        return Geography(level=GeographyLevel.COUNTRY, code="GB", name="United Kingdom")

    @staticmethod
    def defra_applicable_geographies() -> tuple[Geography, ...]:
        # Dataset-level default. Row-level exceptions must be explicit approved mappings.
        return (Geography(level=GeographyLevel.COUNTRY, code="GB", name="United Kingdom"),)
