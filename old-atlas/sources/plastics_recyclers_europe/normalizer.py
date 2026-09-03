from __future__ import annotations

import re
from datetime import UTC, date, datetime

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
from sources.plastics_recyclers_europe.parser import (
    PreModelParameterRow,
    RecycledResinRow,
)


class PlasticsRecyclersEuropeNormalizer:
    mapping_version = "0.1.0"
    official_url = (
        "https://www.plasticsrecyclers.eu/wp-content/uploads/2022/10/"
        "increased-eu-plastics-recycling-targets.pdf"
    )

    def normalize(
        self,
        resin_rows: tuple[RecycledResinRow, ...],
        parameter_rows: tuple[PreModelParameterRow, ...],
        *,
        raw: RawAssetReference,
        dataset_version: str,
        parser_version: str,
    ) -> tuple[
        tuple[CanonicalFactor, ...],
        tuple[SourceObservation, ...],
        dict[str, int],
    ]:
        factors = tuple(
            self._factor(
                row,
                raw=raw,
                dataset_version=dataset_version,
                parser_version=parser_version,
            )
            for row in resin_rows
        )
        observations = tuple(
            self._observation(
                row,
                raw=raw,
                dataset_version=dataset_version,
                parser_version=parser_version,
            )
            for row in parameter_rows
        )
        documented = sum(row.value_basis == "documented" for row in resin_rows)
        return (
            factors,
            observations,
            {
                "normalized_factors": len(factors),
                "lca_results": len(factors),
                "regional_factors": len(factors),
                "documented_resin_results": documented,
                "proxy_resin_results": len(factors) - documented,
                "source_observations": len(observations),
                "default_match_eligible": 0,
            },
        )

    def _factor(
        self,
        row: RecycledResinRow,
        *,
        raw: RawAssetReference,
        dataset_version: str,
        parser_version: str,
    ) -> CanonicalFactor:
        geography = Geography(
            level=GeographyLevel.REGION,
            code="EU28",
            name="European Union 28",
        )
        source_factor_id = f"pre:table28:{row.polymer_key}"
        logical_id = f"atlas:{source_factor_id}"
        value = row.value_kgco2e_per_t_output / 1000
        return CanonicalFactor(
            factor_id=f"{logical_id}:{dataset_version}:{raw.sha256[:12]}",
            logical_factor_id=logical_id,
            source_code="PLASTICS_RECYCLERS_EUROPE",
            dataset_id="eu_plastics_recycling_impact_assessment",
            dataset_version_id=f"pre:{dataset_version}:{raw.sha256[:12]}",
            source_factor_id=source_factor_id,
            name=f"{row.polymer_name} - direct recycling GHG result",
            description=(
                "EU-28 model result for recycling sorted plastic bales into recycled "
                "plastic pellets or flakes"
            ),
            taxonomy_code="atlas.material.recycled_plastics",
            source_category="Mechanical recycling outputs",
            source_subcategory=row.polymer_key,
            activity_type="recycled_plastic_production",
            activity_unit="kg",
            factor_value=value,
            factor_unit="kgCO2e/kg",
            entity_type=EnvironmentalEntityType.LCA_RESULT,
            factor_value_kind=FactorValueKind.CO2E_TOTAL,
            intended_use=FactorIntendedUse.CHARACTERIZATION,
            gases=GasValues(co2e=value),
            origin_geography=geography,
            applicable_geographies=(geography,),
            geography_level=GeographyLevel.REGION,
            geographic_specificity=2,
            geographic_fit_type=GeographicFitType.REGIONAL,
            valid_from=date(2012, 1, 1),
            valid_to=date(2025, 12, 31),
            reference_year=2012,
            methodology=Methodology(
                scope="EU-28 average impact-assessment model",
                lifecycle_stage="mechanical recycling",
                system_boundary="sorted plastic bales to recycled pellets or flakes",
                methodology="PRE / BIO by Deloitte impact-assessment model",
                details={
                    "publication_date": "2015-05-29",
                    "model_baseline_year": 2012,
                    "scenario_years": [2020, 2025],
                    "reported_value_kgco2e_per_t_output": str(row.value_kgco2e_per_t_output),
                    "value_basis": row.value_basis,
                    "upstream_dataset": row.upstream_dataset,
                    "old_assessment_not_current_average": True,
                    "inventory_default_match_excluded": True,
                },
            ),
            data_quality=(
                "documented upstream LCI result"
                if row.value_basis == "documented"
                else "explicit PRE resin proxy assumption"
            ),
            provenance=self._provenance(
                raw,
                parser_version=parser_version,
                page=row.source_page,
                table=row.source_table,
                name=row.polymer_name,
                unit="kgCO2e/t output",
            ),
            created_at=datetime.now(UTC),
        )

    def _observation(
        self,
        row: PreModelParameterRow,
        *,
        raw: RawAssetReference,
        dataset_version: str,
        parser_version: str,
    ) -> SourceObservation:
        return SourceObservation(
            observation_id=(f"pre:{dataset_version}:parameter:{self._slug(row.parameter_key)}"),
            entity_type=EnvironmentalEntityType.CALCULATION_PARAMETER,
            name=row.name,
            value=row.value,
            unit=row.unit,
            reference_year=2012,
            source_category=row.source_category,
            provenance=self._provenance(
                raw,
                parser_version=parser_version,
                page=row.source_page,
                table=row.source_table,
                name=row.name,
                unit=row.unit,
            ),
            attributes={
                "value_role": row.value_role,
                "value_basis": row.value_basis,
                "publication_date": "2015-05-29",
                "model_baseline_year": 2012,
                "scenario_years": [2020, 2025],
                "not_a_canonical_factor": True,
            },
        )

    def _provenance(
        self,
        raw: RawAssetReference,
        *,
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
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
