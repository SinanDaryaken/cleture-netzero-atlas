from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime
from functools import cache
from typing import Any, cast

import pycountry

from atlas.domain.enums import (
    EnvironmentalEntityType,
    FactorIntendedUse,
    FactorValueKind,
    GeographicFitType,
    GeographyDerivation,
    GeographyLevel,
    GeographyRole,
    ProvenanceRole,
)
from atlas.domain.models import (
    CanonicalFactor,
    FactorProvenance,
    GasValues,
    Geography,
    GeographyAssignment,
    Methodology,
    RawAssetReference,
)
from atlas.ingestion.errors import PermanentIngestionError
from sources.wrap.parser import WrapRow


class WrapNormalizer:
    mapping_version = "0.1.0"
    official_download = (
        "https://www.wrap.ngo/sites/default/files/2024-03/WRAP-Emission-Factor-Database-v2.0.xlsx"
    )

    def normalize(
        self,
        rows: tuple[WrapRow, ...],
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
        stages = Counter(row.lifecycle_stage for row in rows)
        fits = Counter(factor.geographic_fit_type.value for factor in factors)
        return factors, {
            "normalized_factors": len(factors),
            "lca_results": len(factors),
            "hestia_gwp100_factors": parts["hestia_gwp100"],
            "refined_factors": parts["refined"],
            "table_hestia_gwp100_factors": parts["hestia_gwp100"],
            "table_refined_factors": parts["refined"],
            "negative_lca_results": sum(factor.factor_value < 0 for factor in factors),
            "country_modelled_factors": fits[GeographicFitType.COUNTRY_MODELLED.value],
            "regional_factors": fits[GeographicFitType.REGIONAL.value],
            "continental_factors": fits[GeographicFitType.CONTINENTAL.value],
            "global_factors": fits[GeographicFitType.GLOBAL.value],
            "proxy_factors": fits[GeographicFitType.PROXY.value],
            "default_match_eligible": 0,
            "excluded_rows": 0,
            **{f"stage_{stage}_factors": count for stage, count in stages.items()},
        }

    def _factor(
        self,
        row: WrapRow,
        *,
        raw: RawAssetReference,
        dataset_version: str,
        parser_version: str,
    ) -> CanonicalFactor:
        identity = json.dumps(
            [
                row.dataset_part,
                row.product,
                row.source_database,
                row.source_database_id,
                row.gpc_classification,
                row.source_year,
                row.origin_region,
                row.applicable_region,
                row.production_system,
                row.intermediate_product,
                row.emission_source,
                row.lsr_category,
                row.flag_category,
                row.functional_unit,
                row.lifecycle_stage,
                str(row.factor_kg_co2e),
                str(row.data_quality_score),
                str(row.standard_deviation),
                row.source_link,
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(identity.encode()).hexdigest()[:24]
        source_factor_id = f"wrap:{row.dataset_part}:{digest}"
        logical_id = f"atlas:{source_factor_id}"
        geography, fit = self._geography(row.applicable_region)
        origin_geography = self._origin_geography(row.origin_region)
        activity_unit = self._activity_unit(row.functional_unit)
        data_quality = row.data_quality_score
        return CanonicalFactor(
            factor_id=f"{logical_id}:{dataset_version}:{raw.sha256[:12]}",
            logical_factor_id=logical_id,
            source_code="WRAP",
            dataset_id="wrap_food_drink_scope3",
            dataset_version_id=f"wrap:{dataset_version}:{raw.sha256[:12]}",
            source_factor_id=source_factor_id,
            name=f"{row.product} [{row.lifecycle_stage}]",
            description=(
                f"WRAP Food & Drink Scope 3 {row.dataset_part} climate result; "
                f"source database {row.source_database}"
            ),
            taxonomy_code="atlas.food",
            source_category=row.source_database_id or row.source_database,
            source_subcategory=row.lifecycle_stage,
            activity_type="food_product_lca",
            activity_unit=activity_unit,
            factor_value=row.factor_kg_co2e,
            factor_unit=f"kgCO2e/{activity_unit}",
            entity_type=EnvironmentalEntityType.LCA_RESULT,
            factor_value_kind=FactorValueKind.CO2E_TOTAL,
            intended_use=FactorIntendedUse.CHARACTERIZATION,
            gases=GasValues(co2e=row.factor_kg_co2e),
            origin_geography=origin_geography,
            applicable_geographies=(geography,),
            geography_roles=(
                GeographyAssignment(
                    role=GeographyRole.PRODUCTION_ORIGIN,
                    geography=origin_geography,
                    derivation=GeographyDerivation.SOURCE_DECLARED,
                    source_field="origin_region",
                    rule_version="wrap-geography-v1",
                    confidence=1.0,
                ),
                GeographyAssignment(
                    role=GeographyRole.CALCULATION_APPLICABILITY,
                    geography=geography,
                    derivation=GeographyDerivation.SOURCE_DECLARED,
                    source_field="applicable_region",
                    rule_version="wrap-geography-v1",
                    confidence=1.0,
                ),
            ),
            geography_level=geography.level,
            geographic_specificity=self._specificity(geography.level),
            geographic_fit_type=fit,
            valid_from=date(2024, 3, 27),
            methodology=Methodology(
                scope="Scope 3 food and drink secondary data",
                lifecycle_stage=row.lifecycle_stage,
                system_boundary=row.lifecycle_stage,
                gwp_standard=("IPCC 2021 GWP100" if row.dataset_part == "hestia_gwp100" else None),
                methodology="WRAP Food & Drink Emission Factor Database v2.0",
                uncertainty=row.standard_deviation,
                details={
                    "dataset_part": row.dataset_part,
                    "source_database": row.source_database,
                    "source_database_id": row.source_database_id,
                    "source_year": row.source_year,
                    "origin_region": row.origin_region,
                    "applicable_region": row.applicable_region,
                    "production_system": row.production_system,
                    "gpc_classification": row.gpc_classification,
                    "intermediate_product": row.intermediate_product,
                    "emission_source": row.emission_source,
                    "lsr_category": row.lsr_category,
                    "flag_category": row.flag_category,
                    "source_link_label": row.source_link,
                    "original_functional_unit": row.functional_unit,
                    "curation_rule": (
                        "preferred HESTIA GWP100 plus curated refined layer; full layer excluded"
                    ),
                    "carbonwarm2_excluded": True,
                },
            ),
            data_quality=data_quality,
            provenance=FactorProvenance(
                role=ProvenanceRole.TOTAL,
                raw_asset_key=raw.object_key,
                original_url=self.official_download,
                downloaded_at=raw.downloaded_at,
                file_checksum=raw.sha256,
                original_file=raw.filename,
                parser_version=parser_version,
                mapping_version=self.mapping_version,
                sheet=row.source_sheet,
                table=row.dataset_part,
                row=row.source_row,
                original_factor_name=row.product,
                original_unit=f"kg CO2e per {row.functional_unit}",
            ),
            created_at=datetime.now(UTC),
        )

    @classmethod
    @cache
    def _geography(cls, value: str) -> tuple[Geography, GeographicFitType]:
        normalized = value.strip()
        base = normalized.split(" - Processing Location", 1)[0].strip()
        if base.lower() == "global":
            return (
                Geography(level=GeographyLevel.GLOBAL, code="GLOBAL", name="Global"),
                GeographicFitType.GLOBAL,
            )
        country = cls._country(base)
        if country is not None:
            return (
                Geography(
                    level=GeographyLevel.COUNTRY,
                    code=country[0],
                    name=country[1],
                ),
                GeographicFitType.COUNTRY_MODELLED,
            )
        if base in {"Europe", "Western Europe", "Region of Europe"}:
            return (
                Geography(level=GeographyLevel.CONTINENT, code="EUROPE", name=base),
                GeographicFitType.CONTINENTAL,
            )
        return (
            Geography(level=GeographyLevel.REGION, code=cls._code(base), name=base),
            GeographicFitType.REGIONAL,
        )

    @classmethod
    def _origin_geography(cls, value: str) -> Geography:
        geography, _ = cls._geography(value)
        return geography

    @staticmethod
    @cache
    def _country(value: str) -> tuple[str, str] | None:
        aliases = {
            "UK": "GB",
            "US": "US",
            "Iran": "IR",
            "Russia": "RU",
        }
        if value in aliases:
            match = pycountry.countries.get(alpha_2=aliases[value])
            return None if match is None else (str(match.alpha_2), str(match.name))
        try:
            matches = pycountry.countries.search_fuzzy(value)
        except LookupError:
            return None
        if not matches:
            return None
        match = cast(Any, matches[0])
        return str(match.alpha_2), str(match.name)

    @staticmethod
    def _activity_unit(functional_unit: str) -> str:
        normalized = functional_unit.lower()
        if "litre" in normalized or "liter" in normalized:
            return "L"
        if "kg" in normalized:
            return "kg"
        raise PermanentIngestionError(f"unmapped WRAP functional unit: {functional_unit}")

    @staticmethod
    def _code(value: str) -> str:
        return "WRAP-" + hashlib.sha256(value.encode()).hexdigest()[:10].upper()

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
