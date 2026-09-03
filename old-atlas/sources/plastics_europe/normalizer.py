from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

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
from sources.plastics_europe.parser import PlasticsEuropeRow


class PlasticsEuropeNormalizer:
    mapping_version = "0.1.0"
    official_url = (
        "https://plasticseurope.org/sustainability/circularity/"
        "life-cycle-thinking/eco-profiles-set/"
    )

    def normalize(
        self,
        rows: tuple[PlasticsEuropeRow, ...],
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
        families = Counter(row.family for row in rows)
        return factors, {
            "normalized_factors": len(factors),
            "lca_results": len(factors),
            "continental_factors": len(factors),
            "default_match_eligible": 0,
            "excluded_rows": 0,
            **{
                f"family_{self._metric_key(family)}_factors": count
                for family, count in families.items()
            },
        }

    def _factor(
        self,
        row: PlasticsEuropeRow,
        *,
        raw: RawAssetReference,
        dataset_version: str,
        parser_version: str,
    ) -> CanonicalFactor:
        geography = Geography(
            level=GeographyLevel.CONTINENT,
            code="EUROPE",
            name="Europe",
        )
        source_factor_id = f"plastics_europe:{row.process_uuid}:gwp100"
        logical_id = f"atlas:{source_factor_id}"
        value = row.gwp100_kgco2e / row.reference_amount
        taxonomy = (
            "atlas.material.plastics"
            if row.package_key in {"pe_and_pp", "cvm_and_pvc"}
            else "atlas.material.chemical_feedstock"
        )
        return CanonicalFactor(
            factor_id=f"{logical_id}:{dataset_version}:{raw.sha256[:12]}",
            logical_factor_id=logical_id,
            source_code="PLASTICS_EUROPE",
            dataset_id="eco_profiles",
            dataset_version_id=(
                f"plastics_europe:{dataset_version}:{raw.sha256[:12]}"
            ),
            source_factor_id=source_factor_id,
            name=f"{row.product_name} [cradle-to-gate]",
            description=(
                "Plastics Europe European production-average Eco-profile "
                "climate-change result"
            ),
            taxonomy_code=taxonomy,
            source_category=row.family,
            source_subcategory=row.product_key,
            activity_type="material_cradle_to_gate_lca",
            activity_unit="kg",
            factor_value=value,
            factor_unit="kgCO2e/kg",
            entity_type=EnvironmentalEntityType.LCA_RESULT,
            factor_value_kind=FactorValueKind.CO2E_TOTAL,
            intended_use=FactorIntendedUse.CHARACTERIZATION,
            gases=GasValues(co2e=value),
            origin_geography=geography,
            applicable_geographies=(geography,),
            geography_level=GeographyLevel.CONTINENT,
            geographic_specificity=1,
            geographic_fit_type=GeographicFitType.CONTINENTAL,
            valid_from=row.valid_from,
            valid_to=row.valid_to,
            reference_year=row.reference_year,
            methodology=Methodology(
                scope="European average production",
                lifecycle_stage="cradle-to-gate production",
                system_boundary="cradle-to-gate",
                gwp_standard="EF 3.1 / IPCC 2021 GWP100",
                methodology="Plastics Europe Eco-profiles methodology v3.1",
                details={
                    "process_uuid": row.process_uuid,
                    "process_name": row.process_name,
                    "reference_flow": "1 kg product at producer gate",
                    "package": row.package_filename,
                    "package_sha256": row.package_sha256,
                    "xml_inventory_member": row.xml_member,
                    "pdf_report_member": row.pdf_member,
                    "background_database": "ecoinvent 3.11",
                    "data_owner": "Plastics Europe",
                    "report_update": "March 2026",
                    "inventory_default_match_excluded": True,
                },
            ),
            provenance=FactorProvenance(
                role=ProvenanceRole.TOTAL,
                raw_asset_key=raw.object_key,
                original_url=row.package_url or self.official_url,
                downloaded_at=raw.downloaded_at,
                file_checksum=raw.sha256,
                original_file=raw.filename,
                parser_version=parser_version,
                mapping_version=self.mapping_version,
                sheet=row.xml_member,
                table=row.pdf_member,
                row=row.source_row,
                column_name="Climate change",
                original_factor_name=row.product_name,
                original_unit="kg CO2 eq / 1 kg product",
            ),
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def _metric_key(value: str) -> str:
        return "_".join(value.lower().replace("/", " ").split())
