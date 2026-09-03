from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime

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
from sources.concito.parser import ConcitoRow


class ConcitoNormalizer:
    mapping_version = "0.1.0"
    official_url = "https://www.thebigclimatedatabase.com/"

    def normalize(
        self,
        rows: tuple[ConcitoRow, ...],
        *,
        raw: RawAssetReference,
        dataset_version: str,
        parser_version: str,
    ) -> tuple[tuple[CanonicalFactor, ...], dict[str, int]]:
        included = tuple(
            row for row in rows if row.lifecycle_stage == "Total" or row.factor_tco2e_per_t != 0
        )
        factors = tuple(
            self._factor(
                row,
                raw=raw,
                dataset_version=dataset_version,
                parser_version=parser_version,
            )
            for row in included
        )
        stages = Counter(row.lifecycle_stage for row in included)
        countries = Counter(row.country_code for row in included)
        return factors, {
            "normalized_factors": len(factors),
            "lca_results": len(factors),
            "excluded_zero_components": len(rows) - len(included),
            "negative_lca_results": sum(factor.factor_value < 0 for factor in factors),
            "country_modelled_factors": len(factors),
            "default_match_eligible": 0,
            "excluded_rows": len(rows) - len(included),
            **{f"stage_{stage}_factors": count for stage, count in stages.items()},
            **{f"country_{country}_factors": count for country, count in countries.items()},
        }

    def _factor(
        self,
        row: ConcitoRow,
        *,
        raw: RawAssetReference,
        dataset_version: str,
        parser_version: str,
    ) -> CanonicalFactor:
        country = pycountry.countries.get(alpha_2=row.country_code)
        if country is None:
            raise PermanentIngestionError(f"unmapped CONCITO country: {row.country_code}")
        geography = Geography(
            level=GeographyLevel.COUNTRY,
            code=str(country.alpha_2),
            name=str(country.name),
        )
        stage_key = row.lifecycle_stage.lower().replace(" ", "_")
        source_factor_id = f"concito:{row.activity_id}:{stage_key}"
        logical_id = f"atlas:{source_factor_id}"
        value = row.factor_tco2e_per_t
        return CanonicalFactor(
            factor_id=f"{logical_id}:{dataset_version}:{raw.sha256[:12]}",
            logical_factor_id=logical_id,
            source_code="CONCITO",
            dataset_id="the_big_climate_database",
            dataset_version_id=f"concito:{dataset_version}:{raw.sha256[:12]}",
            source_factor_id=source_factor_id,
            name=f"{row.product} [{row.lifecycle_stage}]",
            description=("The Big Climate Database market-specific food climate LCA result"),
            taxonomy_code="atlas.food",
            source_category=row.category,
            source_subcategory=row.lifecycle_stage,
            activity_type="food_product_lca",
            activity_unit="kg",
            factor_value=value,
            factor_unit="kgCO2e/kg",
            entity_type=EnvironmentalEntityType.LCA_RESULT,
            factor_value_kind=FactorValueKind.CO2E_TOTAL,
            intended_use=FactorIntendedUse.CHARACTERIZATION,
            gases=GasValues(co2e=value),
            applicable_geographies=(geography,),
            geography_roles=(
                GeographyAssignment(
                    role=GeographyRole.MARKET,
                    geography=geography,
                    derivation=GeographyDerivation.SOURCE_DECLARED,
                    source_field="Country",
                    rule_version="concito-geography-v1",
                    confidence=1.0,
                ),
            ),
            geography_level=GeographyLevel.COUNTRY,
            geographic_specificity=3,
            geographic_fit_type=GeographicFitType.COUNTRY_MODELLED,
            valid_from=date(2024, 9, 23),
            methodology=Methodology(
                scope="Food product at retail",
                lifecycle_stage=row.lifecycle_stage,
                system_boundary="cradle to retail",
                gwp_standard="IPCC 2013 GWP100",
                methodology="The Big Climate Database v1.2 / consequential LCA",
                details={
                    "activity_id": row.activity_id,
                    "market_country": row.country_code,
                    "reference_flow": "1 kg food product at retail",
                    "functional_unit_declared": False,
                    "iso_framework": "ISO 14040:2006 and ISO 14044:2006 with documented exceptions",
                    "background_system": "EXIOBASE hybrid multi-regional input-output",
                    "zero_stage_components_excluded": True,
                },
            ),
            provenance=FactorProvenance(
                role=ProvenanceRole.TOTAL,
                raw_asset_key=raw.object_key,
                original_url=f"https://www.thebigclimatedatabase.com/activity/{row.activity_id}/",
                downloaded_at=raw.downloaded_at,
                file_checksum=raw.sha256,
                original_file=raw.filename,
                parser_version=parser_version,
                mapping_version=self.mapping_version,
                sheet=row.source_member,
                table=row.lifecycle_stage,
                row=row.source_row,
                original_factor_name=row.product,
                original_unit="t CO2e/t",
            ),
            created_at=datetime.now(UTC),
        )
