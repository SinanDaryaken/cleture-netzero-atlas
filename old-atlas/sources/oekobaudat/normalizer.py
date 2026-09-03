from __future__ import annotations

import hashlib
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

import pycountry
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
from atlas.ingestion.errors import PermanentIngestionError
from sources.oekobaudat.parser import OekobaudatRow


class OekobaudatNormalizer:
    def __init__(self, mappings_path: Path) -> None:
        with mappings_path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"ÖKOBAUDAT mappings must contain an object: {mappings_path}")
        self.mapping_version = str(payload["version"])
        self.geographies = dict(payload["geographies"])
        self.units = {str(key): str(value) for key, value in payload["units"].items()}

    def normalize(
        self,
        rows: tuple[OekobaudatRow, ...],
        *,
        raw: RawAssetReference,
        dataset_version: str,
        parser_version: str,
    ) -> tuple[tuple[CanonicalFactor, ...], dict[str, int]]:
        factors = tuple(
            self._factor(
                row,
                raw=raw,
                dataset_version=dataset_version,
                parser_version=parser_version,
            )
            for row in rows
        )
        modules = Counter(row.lifecycle_module for row in rows)
        fits = Counter(factor.geographic_fit_type.value for factor in factors)
        return factors, {
            "normalized_factors": len(factors),
            "lca_results": len(factors),
            "a1_gwp_factors": sum(row.gwp_standard.endswith("+A1") for row in rows),
            "a2_gwp_factors": sum(row.gwp_standard.endswith("+A2") for row in rows),
            "negative_lca_results": sum(factor.factor_value < 0 for factor in factors),
            "country_modelled_factors": fits[GeographicFitType.COUNTRY_MODELLED.value],
            "regional_factors": fits[GeographicFitType.REGIONAL.value],
            "continental_factors": fits[GeographicFitType.CONTINENTAL.value],
            "global_factors": fits[GeographicFitType.GLOBAL.value],
            "default_match_eligible": 0,
            "excluded_rows": 0,
            **{f"module_{module}_factors": count for module, count in modules.items()},
        }

    def _factor(
        self,
        row: OekobaudatRow,
        *,
        raw: RawAssetReference,
        dataset_version: str,
        parser_version: str,
    ) -> CanonicalFactor:
        activity_unit = self.units.get(row.reference_unit)
        if activity_unit is None:
            raise PermanentIngestionError(
                f"unmapped ÖKOBAUDAT reference unit: {row.reference_unit}"
            )
        geography, fit = self._geography(row.geography_code)
        value = row.gwp_total / row.reference_quantity
        scenario_key = hashlib.sha256((row.scenario or "default").encode()).hexdigest()[:12]
        logical_id = (
            f"atlas:oekobaudat:{row.dataset_uuid}:{row.lifecycle_module}:{scenario_key}"
        )
        source_factor_id = (
            f"oekobaudat:{row.dataset_uuid}:{row.lifecycle_module}:{scenario_key}"
        )
        name = row.name_en or row.name_de
        if name is None:  # parser contract; retained for type narrowing
            raise PermanentIngestionError("ÖKOBAUDAT row has no product name")
        valid_to = (
            date(row.valid_until_year, 12, 31) if row.valid_until_year is not None else None
        )
        gwp_components = {
            key: str(component / row.reference_quantity) if component is not None else None
            for key, component in {
                "biogenic": row.gwp_biogenic,
                "fossil": row.gwp_fossil,
                "luluc": row.gwp_luluc,
            }.items()
        }
        original_reference = f"{row.reference_quantity} {row.reference_unit}"
        return CanonicalFactor(
            factor_id=(
                f"{logical_id}:{row.dataset_record_version}:{dataset_version}:"
                f"{raw.sha256[:12]}"
            ),
            logical_factor_id=logical_id,
            source_code="OEKOBAUDAT",
            dataset_id="oekobaudat",
            dataset_version_id=f"oekobaudat:{dataset_version}:{raw.sha256[:12]}",
            source_factor_id=source_factor_id,
            name=f"{name} [{row.lifecycle_module}]",
            description=row.scenario_description or row.reference_flow_name,
            taxonomy_code="atlas.construction_product",
            source_category=row.category_en or row.category_original,
            source_subcategory=row.dataset_type,
            activity_type="construction_product_lca",
            activity_unit=activity_unit,
            factor_value=value,
            factor_unit=f"kgCO2e/{activity_unit}",
            entity_type=EnvironmentalEntityType.LCA_RESULT,
            factor_value_kind=FactorValueKind.CO2E_TOTAL,
            intended_use=FactorIntendedUse.CHARACTERIZATION,
            gases=GasValues(co2e=value),
            origin_geography=geography,
            applicable_geographies=(geography,),
            geography_level=geography.level,
            geographic_specificity=self._specificity(geography.level),
            geographic_fit_type=fit,
            valid_from=row.published_on,
            valid_to=valid_to,
            reference_year=row.reference_year,
            methodology=Methodology(
                lifecycle_stage=row.lifecycle_module,
                system_boundary=f"EN 15804 module {row.lifecycle_module}",
                gwp_standard=row.gwp_standard,
                methodology="ÖKOBAUDAT ILCD+EPD / EN 15804",
                details={
                    "dataset_uuid": row.dataset_uuid,
                    "dataset_record_version": row.dataset_record_version,
                    "dataset_type": row.dataset_type,
                    "conformity": row.conformity,
                    "background_databases": row.background_databases,
                    "declaration_owner": row.declaration_owner,
                    "registration_number": row.registration_number,
                    "registration_body": row.registration_body,
                    "predecessor_uuid": row.predecessor_uuid,
                    "predecessor_version": row.predecessor_version,
                    "reference_flow_uuid": row.reference_flow_uuid,
                    "reference_flow_name": row.reference_flow_name,
                    "original_reference_quantity": str(row.reference_quantity),
                    "original_reference_unit": row.reference_unit,
                    "scenario": row.scenario,
                    "scenario_description": row.scenario_description,
                    "normalized_gwp_components_kgco2e": gwp_components,
                    "building_lca_only": True,
                },
            ),
            provenance=FactorProvenance(
                role=ProvenanceRole.TOTAL,
                raw_asset_key=raw.object_key,
                original_url=row.original_url,
                downloaded_at=raw.downloaded_at,
                file_checksum=raw.sha256,
                original_file=raw.filename,
                parser_version=parser_version,
                mapping_version=self.mapping_version,
                sheet="ÖKOBAUDAT 2024-II",
                table=row.lifecycle_module,
                row=row.source_row,
                column_number=64 if row.gwp_standard.endswith("+A2") else 38,
                column_name=(
                    "GWPtotal (A2)" if row.gwp_standard.endswith("+A2") else "GWP"
                ),
                original_factor_name=f"{name} [{row.lifecycle_module}]",
                original_unit=f"kg CO2 eq / {original_reference}",
            ),
            created_at=datetime.now(UTC),
        )

    def _geography(self, code: str) -> tuple[Geography, GeographicFitType]:
        mapped = self.geographies.get(code)
        if mapped is not None:
            level = GeographyLevel(str(mapped["level"]))
            return (
                Geography(level=level, code=str(mapped["code"]), name=str(mapped["name"])),
                GeographicFitType(str(mapped["fit"])),
            )
        country = pycountry.countries.get(alpha_2=code)
        if country is None:
            raise PermanentIngestionError(f"unmapped ÖKOBAUDAT geography: {code}")
        return (
            Geography(
                level=GeographyLevel.COUNTRY,
                code=str(country.alpha_2),
                name=str(country.name),
            ),
            GeographicFitType.COUNTRY_MODELLED,
        )

    @staticmethod
    def _specificity(level: GeographyLevel) -> int:
        return {
            GeographyLevel.GLOBAL: 0,
            GeographyLevel.CONTINENT: 1,
            GeographyLevel.REGION: 2,
            GeographyLevel.COUNTRY: 3,
            GeographyLevel.STATE: 4,
            GeographyLevel.PROVINCE: 4,
            GeographyLevel.CITY: 5,
            GeographyLevel.GRID: 6,
            GeographyLevel.CUSTOM: 2,
        }[level]
