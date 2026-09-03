from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime

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
from sources.agribalyse.parser import AgribalyseRow


class AgribalyseNormalizer:
    mapping_version = "0.1.0"

    def normalize(
        self,
        rows: tuple[AgribalyseRow, ...],
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
        parts = Counter(row.dataset_part for row in rows)
        geography_fits = Counter(factor.geographic_fit_type.value for factor in factors)
        return factors, {
            "normalized_factors": len(factors),
            "lca_results": len(factors),
            "conventional_factors": parts["conventional"],
            "organic_factors": parts["organic"],
            "food_factors": parts["food"],
            "negative_lca_results": sum(factor.factor_value < 0 for factor in factors),
            "country_modelled_factors": geography_fits["country_modelled"],
            "continental_factors": geography_fits["continental"],
            "proxy_factors": geography_fits["proxy"],
            "default_match_eligible": 0,
            "excluded_rows": 0,
        }

    def _factor(
        self,
        row: AgribalyseRow,
        *,
        raw: RawAssetReference,
        dataset_version: str,
        parser_version: str,
    ) -> CanonicalFactor:
        identity = json.dumps(
            [
                row.dataset_part,
                row.source_code,
                row.name_fr,
                row.lci_name,
                row.season_code,
                row.air_freight_code,
                row.delivery,
                row.packaging,
                row.preparation,
                row.duplicate_index,
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(identity.encode()).hexdigest()[:20]
        source_factor_id = (
            f"agribalyse:food:{row.source_code}:{digest}"
            if row.dataset_part == "food"
            else f"agribalyse:{row.dataset_part}:{digest}"
        )
        logical_id = f"atlas:{source_factor_id}"
        geography, level, fit = self._geography(row.geography_code)
        taxonomy_code = "atlas.food" if row.dataset_part == "food" else "atlas.agriculture"
        activity_type = (
            "food_product_lca" if row.dataset_part == "food" else "agricultural_process_lca"
        )
        return CanonicalFactor(
            factor_id=f"{logical_id}:{dataset_version}",
            logical_factor_id=logical_id,
            source_code="AGRIBALYSE",
            dataset_id="agribalyse",
            dataset_version_id=f"agribalyse:{dataset_version}:{raw.sha256[:12]}",
            source_factor_id=source_factor_id,
            name=row.name_fr,
            description=row.lci_name,
            taxonomy_code=taxonomy_code,
            source_category=row.group or row.production_type,
            source_subcategory=row.subgroup or row.source_category,
            activity_type=activity_type,
            activity_unit="kg",
            factor_value=row.climate_change_kgco2e_per_kg,
            factor_unit="kgCO2e/kg",
            entity_type=EnvironmentalEntityType.LCA_RESULT,
            factor_value_kind=FactorValueKind.CO2E_TOTAL,
            intended_use=FactorIntendedUse.CHARACTERIZATION,
            gases=GasValues(co2e=row.climate_change_kgco2e_per_kg),
            origin_geography=geography,
            applicable_geographies=(geography,),
            geography_level=level,
            geographic_specificity=self._specificity(level),
            geographic_fit_type=fit,
            methodology=Methodology(
                lifecycle_stage=(
                    "cradle_to_consumer" if row.dataset_part == "food" else "farm_gate"
                ),
                system_boundary=(
                    "1 kg product consumed in France"
                    if row.dataset_part == "food"
                    else "1 kg agricultural product at farm gate"
                ),
                methodology="AGRIBALYSE 3.2 / EF 3.1 adapted for SimaPro",
                details={
                    "dataset_part": row.dataset_part,
                    "lci_name": row.lci_name,
                    "season_code": row.season_code,
                    "air_freight_code": row.air_freight_code,
                    "delivery": row.delivery,
                    "packaging": row.packaging,
                    "preparation": row.preparation,
                    "dqr": str(row.dqr) if row.dqr is not None else None,
                    "background_database": "ecoinvent 3.9.1 and WFLDB 3.5",
                    "public_result_only": True,
                },
            ),
            data_quality=str(row.dqr) if row.dqr is not None else None,
            provenance=FactorProvenance(
                role=ProvenanceRole.TOTAL,
                raw_asset_key=raw.object_key,
                original_url=row.original_url,
                downloaded_at=raw.downloaded_at,
                file_checksum=row.member_sha256,
                original_file=row.original_file,
                parser_version=parser_version,
                mapping_version=self.mapping_version,
                sheet=row.source_sheet,
                table=row.dataset_part,
                row=row.source_row,
                original_factor_name=row.name_fr,
                original_unit="kg CO2 eq/kg",
            ),
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def _geography(
        code: str,
    ) -> tuple[Geography, GeographyLevel, GeographicFitType]:
        normalized = code.strip()
        if normalized == "EU":
            return (
                Geography(level=GeographyLevel.CONTINENT, code="EUROPE", name="Europe"),
                GeographyLevel.CONTINENT,
                GeographicFitType.CONTINENTAL,
            )
        if normalized == "WI":
            return (
                Geography(level=GeographyLevel.REGION, code="WI", name="West Indies"),
                GeographyLevel.REGION,
                GeographicFitType.PROXY,
            )
        country = pycountry.countries.get(alpha_2=normalized)
        if country is not None:
            geography = Geography(
                level=GeographyLevel.COUNTRY,
                code=str(country.alpha_2),
                name=str(country.name),
            )
            return geography, GeographyLevel.COUNTRY, GeographicFitType.COUNTRY_MODELLED
        geography = Geography(level=GeographyLevel.CUSTOM, code=normalized, name=normalized)
        return geography, GeographyLevel.CUSTOM, GeographicFitType.PROXY

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
