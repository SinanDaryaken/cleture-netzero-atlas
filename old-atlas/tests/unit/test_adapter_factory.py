from typing import Any, cast

import pytest

from atlas.ingestion import AdapterFactory
from atlas.ingestion.registry import SourceRegistry
from sources.ademe.adapter import AdemeAdapter
from sources.aib.adapter import AibAdapter
from sources.canada.adapter import CanadaAdapter
from sources.cbam.adapter import CbamAdapter
from sources.concito.adapter import ConcitoAdapter
from sources.defra.adapter import DefraAdapter
from sources.epa.adapter import EpaAdapter
from sources.etkb.adapter import EtkbAdapter
from sources.ghg_protocol.adapter import GhgProtocolAdapter
from sources.glec.adapter import GlecAdapter
from sources.ipcc.adapter import IpccAdapter
from sources.oekobaudat.adapter import OekobaudatAdapter
from sources.open_ceda.adapter import OpenCedaAdapter
from sources.plastics_europe.adapter import PlasticsEuropeAdapter
from sources.plastics_recyclers_europe.adapter import PlasticsRecyclersEuropeAdapter
from sources.wrap.adapter import WrapAdapter


def test_factory_loads_manifest_adapters() -> None:
    registry = SourceRegistry.discover(__import__("pathlib").Path("sources"))
    factory = AdapterFactory(repository=cast(Any, object()), storage=cast(Any, object()))

    assert isinstance(factory.create(registry.get("AIB")), AibAdapter)
    assert isinstance(factory.create(registry.get("ADEME")), AdemeAdapter)
    assert isinstance(factory.create(registry.get("CBAM")), CbamAdapter)
    assert isinstance(factory.create(registry.get("CONCITO")), ConcitoAdapter)
    assert isinstance(factory.create(registry.get("CANADA")), CanadaAdapter)
    assert isinstance(factory.create(registry.get("DEFRA")), DefraAdapter)
    assert isinstance(factory.create(registry.get("EPA")), EpaAdapter)
    assert isinstance(factory.create(registry.get("ETKB")), EtkbAdapter)
    assert isinstance(factory.create(registry.get("GLEC")), GlecAdapter)
    assert isinstance(factory.create(registry.get("GHG_PROTOCOL")), GhgProtocolAdapter)
    assert isinstance(factory.create(registry.get("IPCC")), IpccAdapter)
    assert isinstance(factory.create(registry.get("OPEN_CEDA")), OpenCedaAdapter)
    assert isinstance(factory.create(registry.get("OEKOBAUDAT")), OekobaudatAdapter)
    assert isinstance(factory.create(registry.get("PLASTICS_EUROPE")), PlasticsEuropeAdapter)
    assert isinstance(
        factory.create(registry.get("PLASTICS_RECYCLERS_EUROPE")),
        PlasticsRecyclersEuropeAdapter,
    )
    assert isinstance(factory.create(registry.get("WRAP")), WrapAdapter)


def test_factory_rejects_a_class_outside_adapter_contract() -> None:
    registry = SourceRegistry.discover(__import__("pathlib").Path("sources"))
    source = registry.get("EPA").model_copy(
        update={
            "adapter": registry.get("EPA").adapter.model_copy(update={"class_path": "builtins.str"})
        }
    )
    factory = AdapterFactory(repository=cast(Any, object()), storage=cast(Any, object()))

    with pytest.raises(TypeError, match="BaseAtlasSourceAdapter"):
        factory.create(source)
