from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import yaml

from atlas.domain.models import SourceDefinition


class DuplicateSourceCodeError(ValueError):
    pass


class SourceNotFoundError(KeyError):
    pass


class SourceRegistry:
    def __init__(self, sources: Iterable[SourceDefinition] = ()) -> None:
        self._sources: dict[str, SourceDefinition] = {}
        for source in sources:
            self.register(source)

    def register(self, source: SourceDefinition) -> None:
        if source.code in self._sources:
            raise DuplicateSourceCodeError(source.code)
        self._sources[source.code] = source

    def get(self, code: str) -> SourceDefinition:
        normalized = code.upper()
        try:
            return self._sources[normalized]
        except KeyError as error:
            raise SourceNotFoundError(normalized) from error

    def list(self) -> tuple[SourceDefinition, ...]:
        return tuple(self._sources[code] for code in sorted(self._sources))

    @classmethod
    def discover(cls, sources_directory: Path) -> SourceRegistry:
        manifests = sorted(sources_directory.glob("*/manifest.yaml"))
        return cls(cls.load_manifest(path) for path in manifests)

    @staticmethod
    def load_manifest(path: Path) -> SourceDefinition:
        with path.open(encoding="utf-8") as manifest_file:
            payload = yaml.safe_load(manifest_file)
        if not isinstance(payload, dict):
            raise ValueError(f"source manifest must contain a mapping: {path}")
        return SourceDefinition.model_validate(payload)
