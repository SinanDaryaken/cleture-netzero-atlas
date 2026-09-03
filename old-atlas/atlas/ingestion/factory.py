from __future__ import annotations

from importlib import import_module
from typing import Any

from atlas.domain.models import SourceDefinition
from atlas.infrastructure.database.repositories import AtlasRepository
from atlas.ingestion.base import BaseAtlasSourceAdapter
from atlas.ports.storage import ObjectStorage


class AdapterFactory:
    """Build adapters from versioned source manifests, without source switches."""

    def __init__(self, *, repository: AtlasRepository, storage: ObjectStorage) -> None:
        self.repository = repository
        self.storage = storage

    def create(self, source: SourceDefinition) -> BaseAtlasSourceAdapter:
        module_name, separator, class_name = source.adapter.class_path.rpartition(".")
        if not separator or not module_name or not class_name:
            raise ValueError(f"invalid adapter class path: {source.adapter.class_path}")
        try:
            module = import_module(module_name)
            adapter_class: Any = getattr(module, class_name)
        except (ImportError, AttributeError) as error:
            raise ValueError(f"adapter could not be loaded: {source.adapter.class_path}") from error
        if not isinstance(adapter_class, type) or not issubclass(
            adapter_class, BaseAtlasSourceAdapter
        ):
            raise TypeError(
                f"adapter must extend BaseAtlasSourceAdapter: {source.adapter.class_path}"
            )
        return adapter_class(repository=self.repository, storage=self.storage)
