from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

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
from sources.ademe.parser import AdemeRow


class AdemeNormalizer:
    def __init__(self, mappings_path: Path) -> None:
        with mappings_path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"ADEME mappings must contain an object: {mappings_path}")
        self.mapping_version = str(payload["version"])
        self.categories = dict(payload["categories"])
        self.country_aliases = dict(payload["country_aliases"])
        self.units = dict(payload["units"])

    def normalize(
        self,
        rows: tuple[AdemeRow, ...],
        *,
        raw: RawAssetReference,
        dataset_version: str,
        parser_version: str,
    ) -> tuple[tuple[CanonicalFactor, ...], dict[str, int]]:
        posts_by_element: dict[str, list[AdemeRow]] = defaultdict(list)
        for row in rows:
            if row.is_factor_post:
                posts_by_element[row.element_id].append(row)

        factors: list[CanonicalFactor] = []
        excluded_archived_or_source = 0
        excluded_missing_value = 0
        excluded_unmapped_geography = 0
        excluded_unmapped_category = 0
        avoided_emissions = 0
        geography_counts: dict[str, int] = defaultdict(int)

        for row in rows:
            if not row.is_valid_factor_element:
                excluded_archived_or_source += 1
                continue
            if row.total is None or row.unit_fr is None:
                excluded_missing_value += 1
                continue
            taxonomy_code = self._taxonomy_code(row)
            if taxonomy_code is None:
                excluded_unmapped_category += 1
                continue
            geography = self._geography(row)
            if geography is None:
                excluded_unmapped_geography += 1
                continue
            origin, level, fit = geography
            value, activity_unit = self._normalize_value(row.total, row.unit_fr)
            intended_use = (
                FactorIntendedUse.AVOIDED_EMISSIONS if value < 0 else FactorIntendedUse.INVENTORY
            )
            if intended_use == FactorIntendedUse.AVOIDED_EMISSIONS:
                avoided_emissions += 1
            geography_counts[fit.value] += 1
            factors.append(
                self._factor(
                    row,
                    posts=posts_by_element[row.element_id],
                    raw=raw,
                    dataset_version=dataset_version,
                    parser_version=parser_version,
                    taxonomy_code=taxonomy_code,
                    value=value,
                    activity_unit=activity_unit,
                    origin=origin,
                    geography_level=level,
                    geographic_fit=fit,
                    intended_use=intended_use,
                )
            )

        return tuple(factors), {
            "parsed_rows": len(rows),
            "normalized_factors": len(factors),
            "default_match_eligible": len(factors) - avoided_emissions,
            "avoided_emission_factors": avoided_emissions,
            "country_specific_factors": geography_counts["country_specific"],
            "regional_factors": geography_counts["regional"],
            "continental_factors": geography_counts["continental"],
            "global_factors": geography_counts["global"],
            "excluded_archived_or_source_rows": excluded_archived_or_source,
            "excluded_missing_value": excluded_missing_value,
            "excluded_unmapped_geography": excluded_unmapped_geography,
            "excluded_unmapped_category": excluded_unmapped_category,
            "excluded_rows": (
                excluded_archived_or_source
                + excluded_missing_value
                + excluded_unmapped_geography
                + excluded_unmapped_category
            ),
        }

    def _factor(
        self,
        row: AdemeRow,
        *,
        posts: list[AdemeRow],
        raw: RawAssetReference,
        dataset_version: str,
        parser_version: str,
        taxonomy_code: str,
        value: Decimal,
        activity_unit: str,
        origin: Geography,
        geography_level: GeographyLevel,
        geographic_fit: GeographicFitType,
        intended_use: FactorIntendedUse,
    ) -> CanonicalFactor:
        source_factor_id = f"ademe:base-carbone:{row.element_id}"
        logical_id = f"atlas:{source_factor_id}"
        dataset_version_id = f"ademe-base-carbone:{dataset_version}:{raw.sha256[:12]}"
        gas_values = self._gas_values(row)
        return CanonicalFactor(
            factor_id=f"{logical_id}:{dataset_version}",
            logical_factor_id=logical_id,
            source_code="ADEME",
            dataset_id="ademe-base-carbone",
            dataset_version_id=dataset_version_id,
            source_factor_id=source_factor_id,
            name=self._name(row),
            description=row.comment_fr or row.comment_en,
            taxonomy_code=taxonomy_code,
            source_category=row.category_path,
            source_subcategory=row.tags_fr,
            activity_type=taxonomy_code.split(".")[1],
            activity_unit=activity_unit,
            factor_value=value,
            factor_unit=f"kgCO2e/{activity_unit}",
            factor_value_kind=FactorValueKind.CO2E_TOTAL,
            intended_use=intended_use,
            gases=gas_values,
            origin_geography=origin,
            applicable_geographies=(origin,),
            geography_level=geography_level,
            geographic_specificity=self._specificity(geography_level),
            geographic_fit_type=geographic_fit,
            reference_year=self._reference_year(row.validity_period),
            methodology=Methodology(
                lifecycle_stage=self._lifecycle_stage(posts),
                system_boundary=row.boundary_fr or row.boundary_en,
                methodology=row.program or "ADEME Base Carbone",
                uncertainty=row.uncertainty,
                details=self._methodology_details(row, posts),
            ),
            data_quality=(str(row.quality) if row.quality is not None else row.status),
            provenance=FactorProvenance(
                role=ProvenanceRole.TOTAL,
                raw_asset_key=raw.object_key,
                original_url=raw.source_url,
                downloaded_at=raw.downloaded_at,
                file_checksum=raw.sha256,
                original_file=raw.filename,
                parser_version=parser_version,
                mapping_version=self.mapping_version,
                table="Base Carbone",
                row=row.source_row,
                original_factor_name=self._name(row),
                original_unit=row.unit_fr,
            ),
            created_at=datetime.now(UTC),
        )

    def _taxonomy_code(self, row: AdemeRow) -> str | None:
        if row.category_path is None:
            return None
        root = row.category_path.split(">", 1)[0].strip()
        return self.categories.get(root)

    def _normalize_value(self, value: Decimal, source_unit: str) -> tuple[Decimal, str]:
        definition = self.units.get(source_unit)
        if not isinstance(definition, dict):
            raise PermanentIngestionError(f"unknown ADEME factor unit: {source_unit}")
        activity_unit = definition.get("activity_unit")
        divisor = definition.get("divisor")
        if not isinstance(activity_unit, str) or divisor is None:
            raise ValueError(f"invalid ADEME unit mapping: {source_unit}")
        return value / Decimal(str(divisor)), activity_unit

    def _gas_values(self, row: AdemeRow) -> GasValues:
        if row.unit_fr is None or row.total is None:
            return GasValues()
        source_unit = row.unit_fr

        def normalize(component: Decimal | None) -> Decimal | None:
            return (
                self._normalize_value(component, source_unit)[0] if component is not None else None
            )

        ch4_parts = [value for value in (row.ch4_fossil, row.ch4_biogenic) if value is not None]
        return GasValues(
            co2=normalize(row.co2_fossil),
            ch4=normalize(sum(ch4_parts, Decimal(0))) if ch4_parts else None,
            n2o=normalize(row.n2o),
            co2e=self._normalize_value(row.total, source_unit)[0],
        )

    def _geography(
        self, row: AdemeRow
    ) -> tuple[Geography, GeographyLevel, GeographicFitType] | None:
        location = row.geographic_location
        if location == "France continentale":
            return (
                Geography(level=GeographyLevel.COUNTRY, code="FR", name="France"),
                GeographyLevel.COUNTRY,
                GeographicFitType.COUNTRY_SPECIFIC,
            )
        if location == "Outre-mer":
            return (
                Geography(
                    level=GeographyLevel.REGION,
                    code="FR_OVERSEAS",
                    name="French overseas territories",
                ),
                GeographyLevel.REGION,
                GeographicFitType.REGIONAL,
            )
        if location == "Europe":
            return (
                Geography(level=GeographyLevel.CONTINENT, code="EUROPE", name="Europe"),
                GeographyLevel.CONTINENT,
                GeographicFitType.CONTINENTAL,
            )
        if location == "Monde":
            return (
                Geography(level=GeographyLevel.GLOBAL, code="GLOBAL", name="Global"),
                GeographyLevel.GLOBAL,
                GeographicFitType.GLOBAL,
            )
        if location == "Autre pays du monde" and row.sub_location_fr is not None:
            code = self.country_aliases.get(row.sub_location_fr)
            if code is not None:
                return (
                    Geography(
                        level=GeographyLevel.COUNTRY,
                        code=code,
                        name=row.sub_location_en or row.sub_location_fr,
                    ),
                    GeographyLevel.COUNTRY,
                    GeographicFitType.COUNTRY_SPECIFIC,
                )
        return None

    def _methodology_details(self, row: AdemeRow, posts: list[AdemeRow]) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "base_carbone_element_id": row.element_id,
                "source_status": row.status,
                "structure": row.structure,
                "source_unit": row.unit_fr,
                "source": row.source,
                "contributor": row.contributor,
                "other_contributors": row.other_contributors,
                "program_url": row.program_url,
                "geographic_location": row.geographic_location,
                "sub_location": row.sub_location_fr,
                "created_on": row.created_on,
                "modified_on": row.modified_on,
                "validity_period": row.validity_period,
                "transparency": row.transparency,
                "quality": row.quality,
                "co2_biogenic_co2e": row.co2_biogenic,
                "other_ghg_co2e": row.other_ghg,
                "additional_gases_co2e": row.additional_gases or None,
                "decomposition": self._decomposition(posts) or None,
            }.items()
            if value is not None
        }

    @staticmethod
    def _decomposition(posts: list[AdemeRow]) -> list[dict[str, Any]]:
        return [
            {
                key: value
                for key, value in {
                    "source_row": post.source_row,
                    "type": post.post_type,
                    "name": post.post_name_fr or post.post_name_en,
                    "total_co2e": post.total,
                    "co2_fossil_co2e": post.co2_fossil,
                    "ch4_fossil_co2e": post.ch4_fossil,
                    "ch4_biogenic_co2e": post.ch4_biogenic,
                    "n2o_co2e": post.n2o,
                    "other_ghg_co2e": post.other_ghg,
                    "co2_biogenic_co2e": post.co2_biogenic,
                }.items()
                if value is not None
            }
            for post in posts
        ]

    @staticmethod
    def _name(row: AdemeRow) -> str:
        values = (row.name_fr or row.name_en, row.attribute_fr or row.attribute_en)
        name = " / ".join(value for value in values if value)
        return name or f"Base Carbone {row.element_id}"

    @staticmethod
    def _reference_year(value: str | None) -> int | None:
        if value is None:
            return None
        match = re.fullmatch(r"(?:Année\s+)?(19\d{2}|20\d{2})", value.strip())
        return int(match.group(1)) if match is not None else None

    @staticmethod
    def _lifecycle_stage(posts: list[AdemeRow]) -> str | None:
        stages = {post.post_type for post in posts if post.post_type}
        if len(stages) == 1:
            return next(iter(stages))
        if stages:
            return "composite"
        return None

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
