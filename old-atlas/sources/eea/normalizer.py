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
from sources.eea.parser import EeaRow


class EeaNormalizer:
    mapping_version = "0.1.1"

    def normalize(
        self,
        rows: tuple[EeaRow, ...],
        *,
        raw: RawAssetReference,
        dataset_revision: str,
        dataset_version: str,
        index_name: str,
        refreshed_at: str,
        parser_version: str,
    ) -> tuple[
        tuple[CanonicalFactor, ...],
        tuple[SourceObservation, ...],
        dict[str, int],
    ]:
        factors: list[CanonicalFactor] = []
        observations: list[SourceObservation] = []
        excluded_non_numeric = 0
        for row in rows:
            if row.value is None:
                excluded_non_numeric += 1
            elif row.is_canonical_ghg_factor:
                factors.append(
                    self._factor(
                        row,
                        raw=raw,
                        dataset_revision=dataset_revision,
                        dataset_version=dataset_version,
                        index_name=index_name,
                        refreshed_at=refreshed_at,
                        parser_version=parser_version,
                    )
                )
            else:
                observations.append(
                    self._observation(
                        row,
                        raw=raw,
                        dataset_version=dataset_version,
                        index_name=index_name,
                        refreshed_at=refreshed_at,
                        parser_version=parser_version,
                    )
                )
        return (
            tuple(factors),
            tuple(observations),
            {
                "normalized_factors": len(factors),
                "emission_factors": len(factors),
                "source_observations": len(observations),
                "excluded_non_numeric_rows": excluded_non_numeric,
                "excluded_rows": excluded_non_numeric,
                "continental_factors": len(factors),
                "default_match_eligible": 0,
            },
        )

    def _factor(
        self,
        row: EeaRow,
        *,
        raw: RawAssetReference,
        dataset_revision: str,
        dataset_version: str,
        index_name: str,
        refreshed_at: str,
        parser_version: str,
    ) -> CanonicalFactor:
        assert row.value is not None
        geography = Geography(
            level=GeographyLevel.CONTINENT,
            code="EUROPE",
            name="Europe",
        )
        source_factor_id = f"eea:efdb:{row.record_id}"
        logical_id = f"atlas:{source_factor_id}"
        role = {
            "CO2": ProvenanceRole.CO2,
            "CO2 lube": ProvenanceRole.CO2,
            "CH4": ProvenanceRole.CH4,
            "N2O": ProvenanceRole.N2O,
        }[row.pollutant]
        gases = {
            "CO2": GasValues(co2=row.value),
            "CO2 lube": GasValues(co2=row.value),
            "CH4": GasValues(ch4=row.value),
            "N2O": GasValues(n2o=row.value),
        }[row.pollutant]
        value_kind = (
            FactorValueKind.CO2_ONLY
            if row.pollutant in {"CO2", "CO2 lube"}
            else FactorValueKind.GAS_EMISSION_FACTOR
        )
        return CanonicalFactor(
            factor_id=f"{logical_id}:{dataset_revision[:12]}",
            logical_factor_id=logical_id,
            source_code="EEA",
            dataset_id="emep-eea-guidebook-2023-viewer",
            dataset_version_id=f"eea:{dataset_version}:{dataset_revision[:12]}",
            source_factor_id=source_factor_id,
            name=self._name(row),
            description=(
                "Selected gas-specific emission factor from the EMEP/EEA air pollutant "
                "emission inventory guidebook 2023 viewer."
            ),
            taxonomy_code=f"emep_eea.nfr.{self._slug(row.nfr)}",
            source_category=row.sector,
            source_subcategory=row.nfr,
            activity_type=row.sector,
            activity_unit=self._activity_unit(row.unit),
            factor_value=row.value,
            factor_unit=row.unit,
            entity_type=EnvironmentalEntityType.EMISSION_FACTOR,
            factor_value_kind=value_kind,
            intended_use=FactorIntendedUse.INVENTORY,
            gases=gases,
            origin_geography=geography,
            applicable_geographies=(geography,),
            geography_level=GeographyLevel.CONTINENT,
            geographic_specificity=1,
            geographic_fit_type=GeographicFitType.CONTINENTAL,
            valid_from=date(2023, 10, 2),
            reference_year=2023,
            methodology=Methodology(
                scope="national air-emission inventory guidance",
                lifecycle_stage="direct combustion or mobile-source emissions",
                system_boundary=row.sector,
                methodology=f"EMEP/EEA Guidebook 2023 — {row.factor_type}",
                details={
                    "viewer_record_id": row.record_id,
                    "viewer_index": index_name,
                    "viewer_refreshed_at": refreshed_at,
                    "nfr": row.nfr,
                    "category_code": row.category_code,
                    "table": row.table,
                    "technology": row.technology,
                    "fuel": row.fuel,
                    "abatement": row.abatement,
                    "source_region_field": row.region,
                    "pollutant": row.pollutant,
                    "confidence_interval_lower": row.ci_lower,
                    "confidence_interval_upper": row.ci_upper,
                    "reference": row.reference,
                    "chapter_url": row.chapter_url,
                    "guidebook_chapter_prevails_over_viewer": True,
                    "gas_specific_not_co2e_total": True,
                },
            ),
            data_quality="selected EMEP/EEA Guidebook viewer factor; chapter prevails",
            provenance=self._provenance(
                row,
                raw=raw,
                parser_version=parser_version,
                role=role,
            ),
            created_at=datetime.now(UTC),
        )

    def _observation(
        self,
        row: EeaRow,
        *,
        raw: RawAssetReference,
        dataset_version: str,
        index_name: str,
        refreshed_at: str,
        parser_version: str,
    ) -> SourceObservation:
        assert row.value is not None
        is_emission_factor = "Emission Factor" in row.factor_type
        return SourceObservation(
            observation_id=f"eea:{dataset_version}:record:{row.record_id}",
            entity_type=(
                EnvironmentalEntityType.EMISSION_FACTOR
                if is_emission_factor
                else EnvironmentalEntityType.CALCULATION_PARAMETER
            ),
            name=self._name(row),
            value=row.value,
            unit=row.unit or "source unit not stated",
            reference_year=2023,
            gas=row.pollutant or None,
            source_category=row.sector,
            source_subcategory=row.nfr,
            provenance=self._provenance(
                row,
                raw=raw,
                parser_version=parser_version,
                role=ProvenanceRole.TOTAL,
            ),
            attributes={
                "viewer_record_id": row.record_id,
                "viewer_index": index_name,
                "viewer_refreshed_at": refreshed_at,
                "factor_type": row.factor_type,
                "source_unit": row.unit,
                "table": row.table,
                "technology": row.technology,
                "fuel": row.fuel,
                "abatement": row.abatement,
                "source_region_field": row.region,
                "confidence_interval_lower": row.ci_lower,
                "confidence_interval_upper": row.ci_upper,
                "reference": row.reference,
                "chapter_url": row.chapter_url,
                "not_a_canonical_factor": True,
                "not_canonical_reason": (
                    "unsupported_non_ghg_pollutant"
                    if is_emission_factor
                    else "source_calculation_parameter"
                ),
            },
        )

    def _provenance(
        self,
        row: EeaRow,
        *,
        raw: RawAssetReference,
        parser_version: str,
        role: ProvenanceRole,
    ) -> FactorProvenance:
        return FactorProvenance(
            role=role,
            raw_asset_key=raw.object_key,
            original_url=raw.source_url,
            downloaded_at=raw.downloaded_at,
            file_checksum=raw.sha256,
            original_file=raw.filename,
            parser_version=parser_version,
            mapping_version=self.mapping_version,
            table=row.table,
            row=row.record_id,
            original_factor_name=self._name(row),
            original_unit=row.unit,
        )

    @staticmethod
    def _name(row: EeaRow) -> str:
        qualifiers = [row.pollutant, row.fuel, row.technology]
        suffix = " — ".join(value for value in qualifiers if value and value != "NA")
        return f"{row.nfr} {row.sector} — {suffix}" if suffix else f"{row.nfr} {row.sector}"

    @staticmethod
    def _activity_unit(unit: str) -> str:
        _, separator, denominator = unit.partition("/")
        return denominator.strip() if separator and denominator.strip() else "source activity"

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_") or "unclassified"
