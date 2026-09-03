from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import ClassVar

import pycountry

from atlas.domain.enums import (
    EnvironmentalEntityType,
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
from sources.ember.parser import EmberRow


class EmberNormalizer:
    mapping_version = "0.1.0"
    iso3_overrides: ClassVar[dict[str, tuple[str, str]]] = {"XKX": ("XK", "Kosovo")}

    def normalize(
        self,
        rows: tuple[EmberRow, ...],
        *,
        raw: RawAssetReference,
        dataset_revision: str,
        parser_version: str,
    ) -> tuple[tuple[CanonicalFactor, ...], dict[str, int]]:
        factors: list[CanonicalFactor] = []
        null_values = 0
        unmapped_geographies = 0
        negative_references = 0
        for row in rows:
            if row.intensity_gco2e_per_kwh is None:
                null_values += 1
                continue
            geography = self._geography(row)
            if geography is None:
                unmapped_geographies += 1
                continue
            value = row.intensity_gco2e_per_kwh / Decimal(1000)
            is_negative = value < 0
            if is_negative:
                negative_references += 1
            entity_type = (
                EnvironmentalEntityType.REFERENCE_VALUE
                if is_negative
                else EnvironmentalEntityType.EMISSION_FACTOR
            )
            intended_use = (
                FactorIntendedUse.CALCULATION_INPUT if is_negative else FactorIntendedUse.INVENTORY
            )
            code = geography.code.lower()
            logical_id = f"atlas:ember:electricity-carbon-intensity:{code}"
            source_factor_id = f"ember:carbon-intensity:{code}:{row.reference_year}"
            factors.append(
                CanonicalFactor(
                    factor_id=f"{logical_id}:{row.reference_year}:{dataset_revision[:12]}",
                    logical_factor_id=logical_id,
                    source_code="EMBER",
                    dataset_id="ember-yearly-carbon-intensity",
                    dataset_version_id=f"ember-carbon-intensity:{dataset_revision[:12]}",
                    source_factor_id=source_factor_id,
                    name=f"Electricity carbon intensity — {row.entity}",
                    description="Yearly power-sector emissions intensity reported by Ember.",
                    taxonomy_code="atlas.energy.electricity.grid_mix",
                    source_category="Electricity",
                    source_subcategory="Yearly carbon intensity",
                    activity_type="energy",
                    activity_unit="kWh",
                    factor_value=value,
                    factor_unit="kgCO2e/kWh",
                    entity_type=entity_type,
                    factor_value_kind=FactorValueKind.CO2E_TOTAL,
                    intended_use=intended_use,
                    gases=GasValues(co2e=value),
                    origin_geography=geography,
                    applicable_geographies=(geography,),
                    geography_level=geography.level,
                    geographic_specificity=self._specificity(geography.level),
                    geographic_fit_type=self._fit_type(geography.level),
                    reference_year=row.reference_year,
                    methodology=Methodology(
                        scope="scope_2",
                        lifecycle_stage="electricity_generation",
                        system_boundary="power_sector_generation",
                        methodology="Ember Yearly Electricity Data",
                        details={
                            "source_metric": "emissions_intensity_gco2_per_kwh",
                            "source_entity_code": row.entity_code,
                            "is_aggregate_entity": row.is_aggregate_entity,
                            "negative_source_value": is_negative,
                        },
                    ),
                    data_quality="ember_modelled_time_series",
                    provenance=FactorProvenance(
                        role=ProvenanceRole.TOTAL,
                        raw_asset_key=raw.object_key,
                        original_url=raw.source_url,
                        downloaded_at=raw.downloaded_at,
                        file_checksum=raw.sha256,
                        original_file=raw.filename,
                        parser_version=parser_version,
                        mapping_version=self.mapping_version,
                        table="data",
                        row=row.source_row,
                        original_factor_name=(
                            f"{row.entity} {row.reference_year} carbon intensity"
                        ),
                        original_unit="gCO2e/kWh",
                    ),
                    created_at=datetime.now(UTC),
                )
            )
        return tuple(factors), {
            "normalized_factors": len(factors),
            "excluded_null_values": null_values,
            "excluded_unmapped_geography": unmapped_geographies,
            "negative_reference_values": negative_references,
            "excluded_rows": null_values + unmapped_geographies,
            "default_match_eligible": sum(factor.default_match_eligible for factor in factors),
        }

    @staticmethod
    def _geography(row: EmberRow) -> Geography | None:
        if row.entity == "World":
            return Geography(level=GeographyLevel.GLOBAL, code="GLOBAL", name="Global")
        if row.is_aggregate_entity:
            slug = re.sub(r"[^A-Z0-9]+", "_", row.entity.upper()).strip("_")
            return Geography(
                level=GeographyLevel.REGION,
                code=f"EMBER_REGION_{slug}",
                name=row.entity,
            )
        if not row.entity_code:
            return None
        normalized_code = row.entity_code.upper()
        override = EmberNormalizer.iso3_overrides.get(normalized_code)
        if override is not None:
            return Geography(
                level=GeographyLevel.COUNTRY,
                code=override[0],
                name=override[1],
            )
        country = pycountry.countries.get(alpha_3=normalized_code)
        if country is None:
            return None
        return Geography(
            level=GeographyLevel.COUNTRY,
            code=str(country.alpha_2),
            name=row.entity,
        )

    @staticmethod
    def _fit_type(level: GeographyLevel) -> GeographicFitType:
        if level == GeographyLevel.COUNTRY:
            return GeographicFitType.COUNTRY_MODELLED
        if level == GeographyLevel.GLOBAL:
            return GeographicFitType.GLOBAL
        return GeographicFitType.REGIONAL

    @staticmethod
    def _specificity(level: GeographyLevel) -> int:
        return {
            GeographyLevel.GLOBAL: 0,
            GeographyLevel.REGION: 2,
            GeographyLevel.COUNTRY: 3,
        }[level]
