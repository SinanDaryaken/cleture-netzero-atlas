from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from atlas.domain.enums import GeographicFitType, GeographyLevel, ProvenanceRole
from atlas.domain.models import (
    CanonicalFactor,
    FactorProvenance,
    GasValues,
    Methodology,
    RawAssetReference,
)
from atlas.taxonomy import SourceMapping
from atlas.units import UnitEngine
from sources.defra.parser import DefraRow

ROLE_BY_GHG_UNIT = {
    "kg CO2e": ProvenanceRole.TOTAL,
    "kg CO2": ProvenanceRole.CO2,
    "kg CO2e of CO2 per unit": ProvenanceRole.CO2,
    "kg CO2e of CH4 per unit": ProvenanceRole.CH4,
    "kg CO2e of N2O per unit": ProvenanceRole.N2O,
}


class DefraNormalizer:
    def __init__(self, mappings_path: Path, unit_engine: UnitEngine | None = None) -> None:
        self.mapping = SourceMapping(mappings_path)
        self.units = unit_engine or UnitEngine()

    def normalize(
        self,
        rows: tuple[DefraRow, ...],
        *,
        raw: RawAssetReference,
        release_year: int,
        parser_version: str,
    ) -> tuple[tuple[CanonicalFactor, ...], dict[str, int]]:
        groups: dict[str, list[DefraRow]] = defaultdict(list)
        for row in rows:
            groups[row.base_source_id].append(row)

        factors: list[CanonicalFactor] = []
        no_data = 0
        conversion_only = 0
        orphan_component_rows = 0
        for base_id, group in groups.items():
            total = next((row for row in group if row.ghg_unit == "kg CO2e"), None)
            if total is None:
                if all(row.ghg_unit.lower().startswith("kwh") for row in group):
                    conversion_only += len(group)
                else:
                    orphan_component_rows += len(group)
                continue
            if total.value is None:
                no_data += 1
                continue
            normalized_value, activity_unit = self.units.normalize_factor(total.value, total.uom)
            taxonomy_code = self.mapping.taxonomy_code(total.level_1)
            gas_values: dict[ProvenanceRole, Decimal] = {}
            component_provenance: list[FactorProvenance] = []
            for row in group:
                role = ROLE_BY_GHG_UNIT.get(row.ghg_unit)
                if role is None or role == ProvenanceRole.TOTAL or row.value is None:
                    continue
                component_value, component_unit = self.units.normalize_factor(row.value, row.uom)
                if component_unit != activity_unit:
                    continue
                gas_values[role] = component_value
                component_provenance.append(
                    self._provenance(
                        row,
                        raw,
                        role=role,
                        parser_version=parser_version,
                    )
                )
            name = " / ".join(
                value
                for value in (
                    total.level_1,
                    total.level_2,
                    total.level_3,
                    total.level_4,
                    total.column_text,
                )
                if value
            )
            logical_id = f"atlas:defra:{total.logical_key}"
            factors.append(
                CanonicalFactor(
                    factor_id=f"{logical_id}:{release_year}",
                    logical_factor_id=logical_id,
                    source_code="DEFRA",
                    dataset_id="defra",
                    dataset_version_id=f"defra:{release_year}:{raw.sha256[:12]}",
                    source_factor_id=base_id,
                    name=name,
                    taxonomy_code=taxonomy_code,
                    source_category=total.level_1,
                    source_subcategory=total.level_2,
                    activity_type=taxonomy_code.split(".")[1],
                    activity_unit=activity_unit,
                    factor_value=normalized_value,
                    factor_unit=f"kgCO2e/{activity_unit}",
                    gases=GasValues(
                        co2=gas_values.get(ProvenanceRole.CO2),
                        ch4=gas_values.get(ProvenanceRole.CH4),
                        n2o=gas_values.get(ProvenanceRole.N2O),
                        co2e=normalized_value,
                    ),
                    origin_geography=self.mapping.defra_origin_geography(),
                    applicable_geographies=self.mapping.defra_applicable_geographies(),
                    geography_level=GeographyLevel.COUNTRY,
                    geographic_specificity=3,
                    geographic_fit_type=GeographicFitType.COUNTRY_SPECIFIC,
                    reference_year=release_year,
                    methodology=Methodology(scope=total.scope),
                    data_quality="source",
                    provenance=self._provenance(
                        total,
                        raw,
                        role=ProvenanceRole.TOTAL,
                        parser_version=parser_version,
                    ),
                    component_provenance=tuple(component_provenance),
                    created_at=datetime.now(UTC),
                )
            )
        return tuple(factors), {
            "parsed_rows": len(rows),
            "normalized_factors": len(factors),
            "missing_total_values": no_data,
            "conversion_only_rows": conversion_only,
            "orphan_component_rows": orphan_component_rows,
            "excluded_rows": no_data + conversion_only + orphan_component_rows,
        }

    def _provenance(
        self,
        row: DefraRow,
        raw: RawAssetReference,
        *,
        role: ProvenanceRole,
        parser_version: str,
    ) -> FactorProvenance:
        return FactorProvenance(
            role=role,
            raw_asset_key=raw.object_key,
            original_url=raw.source_url,
            downloaded_at=raw.downloaded_at,
            file_checksum=raw.sha256,
            original_file=raw.filename,
            parser_version=parser_version,
            mapping_version=self.mapping.version,
            sheet="Factors by Category",
            row=row.row_number,
            original_factor_name=" / ".join(
                value
                for value in (row.level_1, row.level_2, row.level_3, row.level_4, row.column_text)
                if value
            ),
            original_unit=row.uom,
        )
