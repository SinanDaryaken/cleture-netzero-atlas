from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import yaml

from atlas.domain.enums import (
    FactorIntendedUse,
    FactorValueKind,
    GeographicFitType,
    GeographyLevel,
    ProvenanceRole,
)
from atlas.domain.models import (
    CanonicalFactor,
    FactorProvenance,
    GasValues,
    Geography,
    Methodology,
    RawAssetReference,
)
from atlas.ingestion.errors import PermanentIngestionError
from sources.aib.parser import AibRow


class AibNormalizer:
    def __init__(self, mappings_path: Path) -> None:
        with mappings_path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        if not isinstance(payload, dict) or not isinstance(payload.get("countries"), dict):
            raise ValueError(f"AIB mappings must contain countries: {mappings_path}")
        self.mapping_version = str(payload["version"])
        self.countries = {str(code): str(name) for code, name in payload["countries"].items()}

    def normalize(
        self,
        rows: tuple[AibRow, ...],
        *,
        raw: RawAssetReference,
        release_year: int,
        release_version: str,
        parser_version: str,
    ) -> tuple[tuple[CanonicalFactor, ...], dict[str, int]]:
        factors: list[CanonicalFactor] = []
        for row in rows:
            if not row.available:
                continue
            if row.direct_co2_g_per_kwh is None:
                raise PermanentIngestionError(
                    f"AIB available row has no residual CO2 value: {row.country_code}"
                )
            country_name = self.countries.get(row.country_code)
            if country_name is None:
                raise PermanentIngestionError(f"AIB country mapping is missing: {row.country_code}")
            value = row.direct_co2_g_per_kwh / Decimal(1000)
            logical_id = f"atlas:aib:residual-mix:{row.country_code.lower()}"
            geography = Geography(
                level=GeographyLevel.COUNTRY,
                code=row.country_code,
                name=country_name,
            )
            factors.append(
                CanonicalFactor(
                    factor_id=f"{logical_id}:{release_year}-v{release_version}",
                    logical_factor_id=logical_id,
                    source_code="AIB",
                    dataset_id="aib-residual-mix",
                    dataset_version_id=(
                        f"aib-residual-mix:{release_year}-v{release_version}:{raw.sha256[:12]}"
                    ),
                    source_factor_id=f"aib:residual-mix:{row.country_code.lower()}",
                    name=f"Electricity residual mix — {country_name}",
                    description=(
                        "Direct CO2 emissions of untracked electricity consumption; "
                        "not a lifecycle or total CO2e factor."
                    ),
                    taxonomy_code="atlas.energy.electricity.residual_mix",
                    source_category="Electricity",
                    source_subcategory="Residual mix",
                    activity_type="energy",
                    activity_unit="kWh",
                    factor_value=value,
                    factor_unit="kgCO2/kWh",
                    factor_value_kind=FactorValueKind.CO2_ONLY,
                    intended_use=FactorIntendedUse.INVENTORY,
                    gases=GasValues(co2=value),
                    origin_geography=geography,
                    applicable_geographies=(geography,),
                    geography_level=GeographyLevel.COUNTRY,
                    geographic_specificity=3,
                    geographic_fit_type=GeographicFitType.COUNTRY_SPECIFIC,
                    reference_year=release_year,
                    methodology=Methodology(
                        scope="scope_2",
                        lifecycle_stage="direct_generation",
                        system_boundary="direct_emissions",
                        methodology="Shifted Issuing Based Methodology",
                        details={
                            "residual_mix": True,
                            "use_when_no_guarantees_of_origin_cancelled": True,
                            "direct_co2_only": True,
                            "lifecycle_assessment_included": False,
                            "biogenic_carbon_included": False,
                            "transmission_distribution_losses_explicitly_included": False,
                            "untracked_share": row.untracked_share,
                            "generation_shares": row.shares,
                            "radioactive_waste_mg_per_kwh": (row.radioactive_waste_mg_per_kwh),
                            "residual_mix_source_row": row.residual_mix_row,
                        },
                    ),
                    data_quality="source_reported_no_uncertainty",
                    provenance=FactorProvenance(
                        role=ProvenanceRole.CO2,
                        raw_asset_key=raw.object_key,
                        original_url=raw.source_url,
                        downloaded_at=raw.downloaded_at,
                        file_checksum=raw.sha256,
                        original_file=raw.filename,
                        parser_version=parser_version,
                        mapping_version=self.mapping_version,
                        sheet=row.source_sheet,
                        table="Residual mix CO2",
                        row=row.source_row,
                        original_factor_name=(f"{row.country_code} Residual mix CO2"),
                        original_unit="gCO2/kWh",
                    ),
                    created_at=datetime.now(UTC),
                )
            )
        return tuple(factors), {
            "normalized_factors": len(factors),
            "excluded_full_disclosure": sum(not row.available for row in rows),
            "direct_co2_only_factors": len(factors),
        }
