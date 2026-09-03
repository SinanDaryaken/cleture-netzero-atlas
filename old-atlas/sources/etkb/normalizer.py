from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

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
)
from sources.etkb.parser import EtkbRow

ValueType = Literal["co2", "co2e"]
VALUE_TYPES: tuple[ValueType, ...] = ("co2", "co2e")


class EtkbNormalizer:
    def __init__(self, mappings_path: Path) -> None:
        with mappings_path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"ETKB mappings must contain an object: {mappings_path}")
        self.mapping_version = str(payload["version"])
        self.taxonomy = {
            str(key): str(value) for key, value in dict(payload["taxonomy"]).items()
        }

    def normalize(
        self,
        rows: tuple[EtkbRow, ...],
        *,
        raw: RawAssetReference,
        release_year: int,
        calculation_revision: str,
        parser_version: str,
    ) -> tuple[tuple[CanonicalFactor, ...], dict[str, int]]:
        factors = tuple(
            self._factor(
                row,
                value_type=value_type,
                raw=raw,
                release_year=release_year,
                calculation_revision=calculation_revision,
                parser_version=parser_version,
            )
            for row in rows
            for value_type in VALUE_TYPES
        )
        return factors, {
            "normalized_factors": len(factors),
            "co2_only_factors": sum(
                factor.factor_value_kind == FactorValueKind.CO2_ONLY for factor in factors
            ),
            "co2e_total_factors": sum(
                factor.factor_value_kind == FactorValueKind.CO2E_TOTAL for factor in factors
            ),
            "default_match_eligible": sum(
                factor.default_match_eligible for factor in factors
            ),
            "table_national_generation_factors": sum(
                row.category == "national_generation" for row in rows
            )
            * 2,
            "table_fuel_generation_factors": sum(
                row.category == "fuel_generation" for row in rows
            )
            * 2,
            "table_consumption_point_factors": sum(
                row.category == "consumption_point" for row in rows
            )
            * 2,
            "excluded_rows": 0,
        }

    def _factor(
        self,
        row: EtkbRow,
        *,
        value_type: ValueType,
        raw: RawAssetReference,
        release_year: int,
        calculation_revision: str,
        parser_version: str,
    ) -> CanonicalFactor:
        value = row.co2_t_per_mwh if value_type == "co2" else row.co2e_t_per_mwh
        suffix = "CO₂" if value_type == "co2" else "CO₂e"
        logical_id = f"atlas:etkb:electricity:{row.activity_key}:{value_type}"
        digest = hashlib.sha256(
            f"{release_year}:{calculation_revision}:{raw.sha256}".encode()
        ).hexdigest()[:16]
        country = Geography(level=GeographyLevel.COUNTRY, code="TR", name="Türkiye")
        is_consumption = row.category == "consumption_point"
        source_column = row.co2_column if value_type == "co2" else row.co2e_column
        original_unit = "tCO2/MWh" if value_type == "co2" else "tCO2e/MWh"
        return CanonicalFactor(
            factor_id=f"{logical_id}:{release_year}:r{calculation_revision}:{digest}",
            logical_factor_id=logical_id,
            source_code="ETKB",
            dataset_id="etkb-turkiye-electricity-emission-factors",
            dataset_version_id=(
                f"etkb-electricity:{release_year}:r{calculation_revision}:{raw.sha256[:12]}"
            ),
            source_factor_id=(
                f"etkb:{release_year}:{row.activity_key}:{value_type}:r{calculation_revision}"
            ),
            name=f"{row.activity_name} — {suffix}",
            description=(
                "Official Türkiye electricity consumption-point emission factor."
                if is_consumption
                else "Official Türkiye gross electricity-generation emission factor."
            ),
            taxonomy_code=self.taxonomy[row.category],
            source_category=row.category,
            source_subcategory=row.source_table,
            activity_type="purchased-electricity" if is_consumption else "electricity-generation",
            activity_unit="kWh",
            factor_value=value,
            factor_unit=f"kg{'CO2' if value_type == 'co2' else 'CO2e'}/kWh",
            entity_type=EnvironmentalEntityType.EMISSION_FACTOR,
            factor_value_kind=(
                FactorValueKind.CO2_ONLY
                if value_type == "co2"
                else FactorValueKind.CO2E_TOTAL
            ),
            intended_use=FactorIntendedUse.INVENTORY,
            gases=(GasValues(co2=value) if value_type == "co2" else GasValues(co2e=value)),
            origin_geography=country,
            applicable_geographies=(country,),
            geography_level=GeographyLevel.COUNTRY,
            geographic_specificity=3,
            geographic_fit_type=GeographicFitType.COUNTRY_SPECIFIC,
            reference_year=release_year,
            valid_from=date(release_year, 1, 1),
            valid_to=date(release_year + 1, 1, 1),
            methodology=Methodology(
                scope="scope_2" if is_consumption else "scope_1",
                lifecycle_stage=(
                    "electricity_consumption" if is_consumption else "electricity_generation"
                ),
                system_boundary=(
                    "electricity delivered at the stated grid connection point"
                    if is_consumption
                    else "gross electricity generation at Türkiye power plants"
                ),
                methodology="IEA Emission Factors 2021 database documentation",
                details={
                    "calculation_revision": calculation_revision,
                    "publisher_reported_co2_t_per_mwh": str(row.co2_t_per_mwh),
                    "publisher_reported_co2e_t_per_mwh": str(row.co2e_t_per_mwh),
                    "publisher_reported_co2e_total": value_type == "co2e",
                    "conversion": "t/MWh is numerically equivalent to kg/kWh",
                    "teias_statistics": True,
                    "national_inventory_crf": True,
                    "eea_import_intensity": True,
                },
            ),
            data_quality="ETKB official annual default",
            provenance=FactorProvenance(
                role=ProvenanceRole.CO2 if value_type == "co2" else ProvenanceRole.TOTAL,
                raw_asset_key=raw.object_key,
                original_url=raw.source_url,
                downloaded_at=raw.downloaded_at,
                file_checksum=raw.sha256,
                original_file=raw.filename,
                parser_version=parser_version,
                mapping_version=self.mapping_version,
                sheet=f"Page {row.source_page}",
                table=row.source_table,
                row=row.source_row,
                column_number=source_column,
                column_name=original_unit,
                original_factor_name=row.activity_name,
                original_unit=original_unit,
            ),
            created_at=datetime.now(UTC),
        )
