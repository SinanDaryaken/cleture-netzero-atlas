from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import yaml

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
    SourceObservation,
)
from sources.glec.parser import (
    GlecFuelRow,
    GlecIntensityRow,
    GlecParameterRow,
    GlecRefrigerantRow,
)


class GlecNormalizer:
    def __init__(self, mappings_path: Path) -> None:
        with mappings_path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        if not isinstance(payload, dict) or not isinstance(payload.get("taxonomy"), dict):
            raise ValueError(f"GLEC mappings must contain taxonomy: {mappings_path}")
        self.mapping_version = str(payload["version"])
        self.taxonomy = {str(key): str(value) for key, value in payload["taxonomy"].items()}

    def normalize(
        self,
        fuels: tuple[GlecFuelRow, ...],
        intensities: tuple[GlecIntensityRow, ...],
        refrigerants: tuple[GlecRefrigerantRow, ...],
        parameters: tuple[GlecParameterRow, ...],
        *,
        raw: RawAssetReference,
        version: str,
        parser_version: str,
    ) -> tuple[tuple[CanonicalFactor, ...], tuple[SourceObservation, ...], dict[str, int]]:
        factors: list[CanonicalFactor] = []
        for fuel_row in fuels:
            factors.append(self._fuel_factor(fuel_row, raw, version, parser_version))
        for intensity_row in intensities:
            factors.append(self._intensity_factor(intensity_row, raw, version, parser_version))

        missing_refrigerant_values = 0
        for refrigerant_row in refrigerants:
            if refrigerant_row.gwp100_ar6 is None:
                missing_refrigerant_values += 1
                continue
            factors.append(self._refrigerant_factor(refrigerant_row, raw, version, parser_version))

        observations = tuple(
            self._parameter_observation(row, raw, version, parser_version) for row in parameters
        )
        return (
            tuple(factors),
            observations,
            {
                "normalized_factors": len(factors),
                "fuel_emission_factors": len(fuels),
                "transport_intensity_factors": len(intensities),
                "characterization_factors": len(refrigerants) - missing_refrigerant_values,
                "source_observations": len(observations),
                "excluded_missing_value": missing_refrigerant_values,
                "default_match_eligible": len(fuels) + len(intensities),
                "global_factors": sum(
                    factor.geographic_fit_type == GeographicFitType.GLOBAL for factor in factors
                ),
                "continental_factors": sum(
                    factor.geographic_fit_type == GeographicFitType.CONTINENTAL
                    for factor in factors
                ),
                "regional_factors": sum(
                    factor.geographic_fit_type == GeographicFitType.REGIONAL for factor in factors
                ),
                "country_specific_factors": sum(
                    factor.geographic_fit_type == GeographicFitType.COUNTRY_SPECIFIC
                    for factor in factors
                ),
            },
        )

    def _fuel_factor(
        self,
        row: GlecFuelRow,
        raw: RawAssetReference,
        version: str,
        parser_version: str,
    ) -> CanonicalFactor:
        geography, fit, specificity = self._geography(row.geography_code, row.geography_name)
        identity = self._slug(
            "-".join(
                part for part in (row.geography_code, row.energy_carrier, row.application) if part
            )
        )
        value = row.wtw_g_co2e_per_mj / Decimal(1000)
        name = f"{row.energy_carrier} - WTW fuel emission factor"
        if row.application:
            name = f"{name} ({row.application})"
        return CanonicalFactor(
            factor_id=f"atlas:glec:fuel:{identity}:v{version}",
            logical_factor_id=f"atlas:glec:fuel:{identity}",
            source_code="GLEC",
            dataset_id="glec-framework",
            dataset_version_id=f"glec-framework:v{version}:{raw.sha256[:12]}",
            source_factor_id=f"glec:fuel:{identity}",
            name=name,
            description="GLEC Framework v3.2 well-to-wheel fuel or energy carrier factor.",
            taxonomy_code=self.taxonomy["fuel"],
            source_category="Module 1 - Fuel emission factors",
            source_subcategory=row.source_table,
            activity_type="transport-energy",
            activity_unit="MJ",
            factor_value=value,
            factor_unit="kgCO2e/MJ",
            factor_value_kind=FactorValueKind.CO2E_TOTAL,
            intended_use=FactorIntendedUse.INVENTORY,
            gases=GasValues(co2e=value),
            origin_geography=geography,
            applicable_geographies=(geography,),
            geography_level=geography.level,
            geographic_specificity=specificity,
            geographic_fit_type=fit,
            reference_year=2025,
            methodology=Methodology(
                lifecycle_stage="well-to-wheel",
                system_boundary="fuel production and transport operation",
                gwp_standard="IPCC AR6 GWP100",
                methodology="GLEC Framework v3.2 / ISO 14083 aligned defaults",
                details={
                    "source_ttw_g_co2e_per_mj": str(row.ttw_g_co2e_per_mj),
                    "source_wtw_g_co2e_per_mj": str(row.wtw_g_co2e_per_mj),
                    "application": row.application,
                },
            ),
            data_quality="GLEC default",
            provenance=self._provenance(
                raw,
                parser_version,
                row.source_page,
                row.source_table,
                name,
                "gCO2e/MJ",
            ),
            created_at=datetime.now(UTC),
        )

    def _intensity_factor(
        self,
        row: GlecIntensityRow,
        raw: RawAssetReference,
        version: str,
        parser_version: str,
    ) -> CanonicalFactor:
        geography, fit, specificity = self._geography(row.geography_code, row.geography_name)
        identity = self._slug(
            "-".join(
                part
                for part in (
                    row.mode,
                    row.geography_code,
                    row.category,
                    row.detail,
                    row.fuel,
                )
                if part
            )
        )
        divisor = Decimal(1000) if row.source_unit.startswith("gCO2e/") else Decimal(1)
        value = row.wtw_value / divisor
        unit = f"kgCO2e/{row.activity_unit}"
        name_parts = [row.category]
        if row.detail:
            name_parts.append(row.detail)
        if row.fuel:
            name_parts.append(row.fuel)
        name = " - ".join(name_parts)
        details: dict[str, object] = dict(row.attributes)
        details.update(
            {
                "source_wtt_value": str(row.wtt_value) if row.wtt_value is not None else None,
                "source_ttw_value": str(row.ttw_value) if row.ttw_value is not None else None,
                "source_wtw_value": str(row.wtw_value),
                "source_unit": row.source_unit,
                "aggregate_value": (
                    str(row.aggregate_value) if row.aggregate_value is not None else None
                ),
            }
        )
        return CanonicalFactor(
            factor_id=f"atlas:glec:intensity:{identity}:v{version}",
            logical_factor_id=f"atlas:glec:intensity:{identity}",
            source_code="GLEC",
            dataset_id="glec-framework",
            dataset_version_id=f"glec-framework:v{version}:{raw.sha256[:12]}",
            source_factor_id=f"glec:intensity:{identity}",
            name=name,
            description="GLEC Framework v3.2 default end-user WTW logistics emission intensity.",
            taxonomy_code=self.taxonomy[row.mode],
            source_category="Module 2 - Default GHG emission intensity values",
            source_subcategory=row.source_table,
            activity_type=row.mode,
            activity_unit=row.activity_unit,
            factor_value=value,
            factor_unit=unit,
            factor_value_kind=FactorValueKind.CO2E_TOTAL,
            intended_use=FactorIntendedUse.INVENTORY,
            gases=GasValues(co2e=value),
            origin_geography=geography,
            applicable_geographies=(geography,),
            geography_level=geography.level,
            geographic_specificity=specificity,
            geographic_fit_type=fit,
            reference_year=2025,
            methodology=Methodology(
                lifecycle_stage="well-to-wheel",
                system_boundary="logistics transport or hub operation",
                gwp_standard="IPCC AR6 GWP100",
                methodology="GLEC Framework v3.2 / ISO 14083 aligned defaults",
                details=details,
            ),
            data_quality="GLEC default",
            provenance=self._provenance(
                raw,
                parser_version,
                row.source_page,
                row.source_table,
                name,
                row.source_unit,
            ),
            created_at=datetime.now(UTC),
        )

    def _refrigerant_factor(
        self,
        row: GlecRefrigerantRow,
        raw: RawAssetReference,
        version: str,
        parser_version: str,
    ) -> CanonicalFactor:
        if row.gwp100_ar6 is None:
            raise ValueError("refrigerant characterization factor requires a value")
        global_geography = Geography(level=GeographyLevel.GLOBAL, code="GLOBAL", name="Global")
        identity = self._slug(row.refrigerant)
        return CanonicalFactor(
            factor_id=f"atlas:glec:refrigerant:{identity}:v{version}",
            logical_factor_id=f"atlas:glec:refrigerant:{identity}",
            source_code="GLEC",
            dataset_id="glec-framework",
            dataset_version_id=f"glec-framework:v{version}:{raw.sha256[:12]}",
            source_factor_id=f"glec:refrigerant:{identity}",
            name=f"{row.refrigerant} GWP100 (AR6)",
            description=row.alternative_name,
            taxonomy_code=self.taxonomy["refrigerant"],
            source_category="Module 3 - Refrigerant emission factors",
            source_subcategory=row.chemical_formula,
            activity_type="refrigerant-characterization",
            activity_unit="kg_refrigerant",
            factor_value=row.gwp100_ar6,
            factor_unit="kgCO2e/kg_refrigerant",
            entity_type=EnvironmentalEntityType.CHARACTERIZATION_RESULT,
            factor_value_kind=FactorValueKind.CHARACTERIZATION_FACTOR,
            intended_use=FactorIntendedUse.CHARACTERIZATION,
            gases=GasValues(),
            origin_geography=global_geography,
            applicable_geographies=(global_geography,),
            geography_level=GeographyLevel.GLOBAL,
            geographic_specificity=0,
            geographic_fit_type=GeographicFitType.GLOBAL,
            reference_year=2025,
            methodology=Methodology(
                lifecycle_stage="characterization",
                system_boundary="refrigerant loss",
                gwp_standard="IPCC AR6 GWP100",
                methodology="GLEC Framework v3.2 refrigerant characterization",
                details={"chemical_formula": row.chemical_formula},
            ),
            data_quality="GLEC default",
            provenance=self._provenance(
                raw,
                parser_version,
                row.source_page,
                row.source_table,
                row.refrigerant,
                "gCO2e/g",
            ),
            created_at=datetime.now(UTC),
        )

    def _parameter_observation(
        self,
        row: GlecParameterRow,
        raw: RawAssetReference,
        version: str,
        parser_version: str,
    ) -> SourceObservation:
        identity = self._slug(f"{row.equipment_type}-{row.name}")
        return SourceObservation(
            observation_id=f"glec:v{version}:parameter:{identity}",
            entity_type=EnvironmentalEntityType.CALCULATION_PARAMETER,
            name=f"{row.name} - {row.equipment_type}",
            value=row.value,
            unit=row.unit,
            reference_year=2025,
            source_category="Module 3 - Refrigerant loss defaults",
            provenance=self._provenance(
                raw,
                parser_version,
                row.source_page,
                row.source_table,
                row.name,
                row.unit,
            ),
            attributes={"equipment_type": row.equipment_type},
        )

    def _provenance(
        self,
        raw: RawAssetReference,
        parser_version: str,
        page: int,
        table: str,
        name: str,
        unit: str,
    ) -> FactorProvenance:
        return FactorProvenance(
            role=ProvenanceRole.TOTAL,
            raw_asset_key=raw.object_key,
            original_url=raw.source_url,
            downloaded_at=raw.downloaded_at,
            file_checksum=raw.sha256,
            original_file=raw.filename,
            parser_version=parser_version,
            mapping_version=self.mapping_version,
            sheet=f"PDF page {page}",
            table=table,
            row=page,
            original_factor_name=name,
            original_unit=unit,
        )

    @staticmethod
    def _geography(code: str, name: str) -> tuple[Geography, GeographicFitType, int]:
        if code == "GLOBAL":
            return (
                Geography(level=GeographyLevel.GLOBAL, code=code, name=name),
                GeographicFitType.GLOBAL,
                0,
            )
        if code in {"CN", "IN"}:
            return (
                Geography(level=GeographyLevel.COUNTRY, code=code, name=name),
                GeographicFitType.COUNTRY_SPECIFIC,
                3,
            )
        if code in {"EU", "NA"}:
            return (
                Geography(level=GeographyLevel.CONTINENT, code=code, name=name),
                GeographicFitType.CONTINENTAL,
                1,
            )
        return (
            Geography(level=GeographyLevel.REGION, code=code, name=name),
            GeographicFitType.REGIONAL,
            2,
        )

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
