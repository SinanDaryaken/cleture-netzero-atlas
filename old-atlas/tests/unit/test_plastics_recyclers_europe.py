from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from atlas.domain.enums import EnvironmentalEntityType, FactorIntendedUse
from atlas.domain.models import RawAssetReference
from sources.plastics_recyclers_europe.normalizer import (
    PlasticsRecyclersEuropeNormalizer,
)
from sources.plastics_recyclers_europe.parser import (
    PlasticsRecyclersEuropeParser,
)


def _pages(_: Path) -> tuple[str, ...]:
    pages = [""] * 54
    pages[0] = "29 May 2015 Increased EU Plastics Recycling Targets"
    pages[31] = " ".join(
        (
            "Plastic waste collection emission factor resulting from these conditions "
            "is 17.36 g CO2e/kg",
            "emission factor at the sorting step is 26.5 kg CO2e/t",
            "Transportation of plastics to recyclers to recyclers is estimated at 21.88 g CO2e/kg",
            "incinerators or landfills is estimated at 2.76 g CO2e/kg",
        )
    )
    pages[32] = " ".join(
        (
            "Table 28 Direct GHG emissions 510 / 280 348 348 348 348 348 348 from recycling",
            "Table 29 Direct GHG emission from 2 150 / 2 050 1 800 1 870 1 630 "
            "3 300 1 900 4 800 virgin plastics production",
        )
    )
    pages[33] = " ".join(
        (
            "incineration is calculated at 2 697 kg CO2e/t",
            "co-incineration of RDF is calculated at 2 697 kg CO2e/t",
            "avoided emissions from incineration is therefore estimated at 2 079 kg CO2e/t",
            "Avoided emissions from RDF/SRF resulting GHG emissions factor is 2 594 kg CO2e/t",
            "Landfilling of plastics",
        )
    )
    pages[34] = "factor 10 kg CO2e/tonne is used Assessment of scenarios"
    return tuple(pages)


def test_pre_parser_separates_recycled_resin_results_and_model_inputs(
    tmp_path: Path,
) -> None:
    parser = PlasticsRecyclersEuropeParser(page_text_extractor=_pages)

    document = parser.parse(tmp_path / "pre.pdf")

    assert len(document.resin_results) == 8
    assert len(document.parameters) == 17
    assert document.resin_results[0].value_kgco2e_per_t_output == Decimal("510")
    assert document.resin_results[1].value_kgco2e_per_t_output == Decimal("280")
    assert [row.value_basis for row in document.resin_results].count("documented") == 4
    assert [row.value_basis for row in document.resin_results].count("proxy_from_pe") == 4
    assert document.parameters[4].parameter_key == "virgin_pet_bottle"
    assert document.parameters[4].value == Decimal("2150")
    assert document.parameters[-1].parameter_key == "landfill"


def test_pre_normalizer_preserves_lca_proxy_and_parameter_boundaries(
    tmp_path: Path,
) -> None:
    document = PlasticsRecyclersEuropeParser(page_text_extractor=_pages).parse(tmp_path / "pre.pdf")
    raw = RawAssetReference(
        bucket="atlas",
        object_key="sources/pre/impact-assessment.pdf",
        sha256="d" * 64,
        filename="impact-assessment.pdf",
        source_url="https://www.plasticsrecyclers.eu/impact-assessment.pdf",
        size_bytes=42,
        downloaded_at="2026-08-28T00:00:00Z",
    )

    factors, observations, metrics = PlasticsRecyclersEuropeNormalizer().normalize(
        document.resin_results,
        document.parameters,
        raw=raw,
        dataset_version=document.version,
        parser_version="0.1.0",
    )

    assert len(factors) == 8
    assert len(observations) == 17
    assert metrics["documented_resin_results"] == 4
    assert metrics["proxy_resin_results"] == 4
    assert factors[0].factor_value == Decimal("0.51")
    assert factors[1].factor_value == Decimal("0.28")
    assert all(factor.entity_type == EnvironmentalEntityType.LCA_RESULT for factor in factors)
    assert all(factor.intended_use == FactorIntendedUse.CHARACTERIZATION for factor in factors)
    assert all(not factor.default_match_eligible for factor in factors)
    assert all(factor.origin_geography.code == "EU28" for factor in factors)
    assert all(
        observation.entity_type == EnvironmentalEntityType.CALCULATION_PARAMETER
        for observation in observations
    )
