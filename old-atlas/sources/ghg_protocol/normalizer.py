from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import ClassVar

import yaml

from atlas.domain.enums import (
    EnvironmentalEntityType,
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
from sources.ghg_protocol.parser import GhgProtocolFactorRow, GhgProtocolObservationRow


class GhgProtocolNormalizer:
    CH4_GWP_AR5 = Decimal(28)
    N2O_GWP_AR5 = Decimal(265)
    _COUNTRY_CODES: ClassVar[set[str]] = {"US", "GB", "CN", "TW", "BR", "TH"}
    _MASS_TO_KG: ClassVar[dict[str, Decimal]] = {
        "kg": Decimal(1),
        "g": Decimal("0.001"),
        "lb": Decimal("0.45359237"),
        "t": Decimal(1000),
    }
    _DENOMINATORS: ClassVar[dict[str, tuple[str, Decimal]]] = {
        "TJ": ("GJ", Decimal(1000)),
        "tonne": ("tonne", Decimal(1)),
        "L": ("l", Decimal(1)),
        "litre": ("l", Decimal(1)),
        "US Gallon": ("l", Decimal("3.785411784")),
        "m3": ("m3", Decimal(1)),
        "scf": ("m3", Decimal("0.028316846592")),
        "km": ("km", Decimal(1)),
        "mile": ("km", Decimal("1.609344")),
        "passenger-kilometer": ("passenger.km", Decimal(1)),
        "passenger-mile": ("passenger.km", Decimal("1.609344")),
        "tonne-kilometer": ("tonne.km", Decimal(1)),
        "short ton-mile": ("tonne.km", Decimal("1.4599729901184")),
        "vehicle-kilometer": ("vehicle.km", Decimal(1)),
        "vehicle-mile": ("vehicle.km", Decimal("1.609344")),
        "kWh": ("kWh", Decimal(1)),
        "MWh": ("kWh", Decimal(1000)),
        "GWh": ("kWh", Decimal(1_000_000)),
    }

    def __init__(self, mappings_path: Path) -> None:
        with mappings_path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        if not isinstance(payload, dict) or not isinstance(payload.get("taxonomy"), dict):
            raise ValueError(f"GHG Protocol mappings must contain taxonomy: {mappings_path}")
        self.mapping_version = str(payload["version"])
        self.taxonomy = {str(key): str(value) for key, value in payload["taxonomy"].items()}
        self.grid_codes = {
            str(key): str(value) for key, value in dict(payload.get("grid_codes", {})).items()
        }

    def normalize(
        self,
        factors: tuple[GhgProtocolFactorRow, ...],
        observations: tuple[GhgProtocolObservationRow, ...],
        *,
        raw: RawAssetReference,
        version: str,
        parser_version: str,
    ) -> tuple[tuple[CanonicalFactor, ...], tuple[SourceObservation, ...], dict[str, int]]:
        normalized: list[CanonicalFactor] = []
        excluded_ranges = 0
        for row in factors:
            if any(
                isinstance(value, str) for value in (row.co2, row.ch4, row.n2o, row.direct_co2e)
            ):
                excluded_ranges += 1
                continue
            normalized.append(self._factor(row, raw, version, parser_version))
        source_observations = tuple(
            self._observation(row, raw, version, parser_version) for row in observations
        )
        return (
            tuple(normalized),
            source_observations,
            {
                "normalized_factors": len(normalized),
                "source_observations": len(source_observations),
                "conversion_observations": sum(
                    row.observation_kind == "conversion_factor" for row in observations
                ),
                "technical_property_observations": sum(
                    row.observation_kind == "technical_property" for row in observations
                ),
                "excluded_range_values": excluded_ranges,
                "co2e_total_factors": sum(
                    factor.factor_value_kind == FactorValueKind.CO2E_TOTAL for factor in normalized
                ),
                "co2_only_factors": sum(
                    factor.factor_value_kind == FactorValueKind.CO2_ONLY for factor in normalized
                ),
                "non_co2_factors": sum(
                    factor.factor_value_kind == FactorValueKind.NON_CO2_CO2E
                    for factor in normalized
                ),
                "default_match_eligible": sum(
                    factor.default_match_eligible for factor in normalized
                ),
                "global_factors": sum(
                    factor.geographic_fit_type == GeographicFitType.GLOBAL for factor in normalized
                ),
                "regional_factors": sum(
                    factor.geographic_fit_type == GeographicFitType.REGIONAL
                    for factor in normalized
                ),
                "country_specific_factors": sum(
                    factor.geographic_fit_type == GeographicFitType.COUNTRY_SPECIFIC
                    for factor in normalized
                ),
            },
        )

    def _factor(
        self,
        row: GhgProtocolFactorRow,
        raw: RawAssetReference,
        version: str,
        parser_version: str,
    ) -> CanonicalFactor:
        activity_unit, co2 = self._component(row.co2, row.co2_unit, row.denominator_unit)
        ch4_unit, ch4 = self._component(row.ch4, row.ch4_unit, row.denominator_unit)
        n2o_unit, n2o = self._component(row.n2o, row.n2o_unit, row.denominator_unit)
        direct_unit, direct = self._component(
            row.direct_co2e, row.direct_co2e_unit, row.denominator_unit
        )
        units = {unit for unit in (activity_unit, ch4_unit, n2o_unit, direct_unit) if unit}
        if len(units) != 1:
            raise ValueError(
                f"GHG Protocol component units do not align for {row.source_key}: {units}"
            )
        canonical_unit = units.pop()
        if direct is not None:
            factor_value = direct
        elif row.factor_value_kind == FactorValueKind.CO2_ONLY:
            factor_value = co2 or Decimal(0)
        elif row.factor_value_kind == FactorValueKind.NON_CO2_CO2E:
            factor_value = (ch4 or Decimal(0)) * self.CH4_GWP_AR5 + (
                n2o or Decimal(0)
            ) * self.N2O_GWP_AR5
        else:
            factor_value = (
                (co2 or Decimal(0))
                + (ch4 or Decimal(0)) * self.CH4_GWP_AR5
                + (n2o or Decimal(0)) * self.N2O_GWP_AR5
            )
        geography, applicable, fit, specificity = self._geography(row)
        identity = self._slug(row.source_key)
        factor_unit = (
            f"kgCO2/{canonical_unit}"
            if row.factor_value_kind == FactorValueKind.CO2_ONLY
            else f"kgCO2e/{canonical_unit}"
        )
        component_provenance = tuple(
            self._provenance(row, raw, parser_version, role)
            for value, role in (
                (co2, ProvenanceRole.CO2),
                (ch4, ProvenanceRole.CH4),
                (n2o, ProvenanceRole.N2O),
            )
            if value is not None
        )
        return CanonicalFactor(
            factor_id=f"atlas:ghg-protocol:{identity}:v{version}",
            logical_factor_id=f"atlas:ghg-protocol:{identity}",
            source_code="GHG_PROTOCOL",
            dataset_id="ghg-protocol-cross-sector",
            dataset_version_id=f"ghg-protocol-cross-sector:v{version}:{raw.sha256[:12]}",
            source_factor_id=f"ghg-protocol:{identity}",
            name=row.name,
            description="GHG Protocol Cross-sector Emission Factors v2.0 compiled default.",
            taxonomy_code=self.taxonomy[row.activity_type],
            source_category=row.category,
            source_subcategory=row.source_table,
            activity_type=row.activity_type,
            activity_unit=canonical_unit,
            factor_value=factor_value,
            factor_unit=factor_unit,
            factor_value_kind=row.factor_value_kind,
            intended_use=row.intended_use,
            gases=GasValues(co2=co2, ch4=ch4, n2o=n2o, co2e=factor_value),
            origin_geography=geography,
            applicable_geographies=applicable,
            geography_level=geography.level,
            geographic_specificity=specificity,
            geographic_fit_type=fit,
            reference_year=row.reference_year,
            methodology=Methodology(
                scope=row.scope,
                lifecycle_stage=row.lifecycle_stage,
                system_boundary=row.system_boundary,
                gwp_standard=(
                    None if row.factor_value_kind == FactorValueKind.CO2_ONLY else "IPCC AR5 GWP100"
                ),
                methodology="GHG Protocol Cross-sector Emission Factors v2.0 compilation",
                details={
                    **row.attributes,
                    "original_source": row.original_source,
                    "derivation": self._derivation(row),
                    "source_denominator_unit": row.denominator_unit,
                },
            ),
            data_quality="GHG Protocol default; prefer supplier- or country-specific data",
            provenance=self._provenance(row, raw, parser_version, ProvenanceRole.TOTAL),
            component_provenance=component_provenance,
            created_at=datetime.now(UTC),
        )

    def _observation(
        self,
        row: GhgProtocolObservationRow,
        raw: RawAssetReference,
        version: str,
        parser_version: str,
    ) -> SourceObservation:
        identity = self._slug(f"{row.source_table}-{row.name}-{row.unit}")
        entity_type = (
            EnvironmentalEntityType.CONVERSION_FACTOR
            if row.observation_kind == "conversion_factor"
            else EnvironmentalEntityType.TECHNICAL_PROPERTY
        )
        return SourceObservation(
            observation_id=f"ghg-protocol:v{version}:{row.observation_kind}:{identity}",
            entity_type=entity_type,
            name=row.name,
            value=row.value,
            unit=row.unit,
            reference_year=row.reference_year,
            source_category=row.category,
            source_subcategory=row.source_table,
            provenance=FactorProvenance(
                role=ProvenanceRole.TOTAL,
                raw_asset_key=raw.object_key,
                original_url=raw.source_url,
                downloaded_at=raw.downloaded_at,
                file_checksum=raw.sha256,
                original_file=raw.filename,
                parser_version=parser_version,
                mapping_version=self.mapping_version,
                sheet=row.source_sheet,
                table=row.source_table,
                row=row.source_row,
                column_number=row.source_column,
                original_factor_name=row.name,
                original_unit=row.unit,
            ),
            attributes=row.attributes,
        )

    def _geography(
        self, row: GhgProtocolFactorRow
    ) -> tuple[Geography, tuple[Geography, ...], GeographicFitType, int]:
        if row.geography_code == "GLOBAL":
            geography = Geography(level=GeographyLevel.GLOBAL, code="GLOBAL", name="Global")
            return geography, (geography,), GeographicFitType.GLOBAL, 0
        if row.geography_code in self._COUNTRY_CODES:
            geography = Geography(
                level=GeographyLevel.COUNTRY,
                code=row.geography_code,
                name=row.geography_name,
            )
            return geography, (geography,), GeographicFitType.COUNTRY_SPECIFIC, 3
        country = Geography(level=GeographyLevel.COUNTRY, code="US", name="United States")
        grid_code = self.grid_codes.get(row.geography_code)
        if grid_code:
            geography = Geography(
                level=GeographyLevel.GRID,
                code=grid_code,
                name=row.geography_name,
            )
            return geography, (geography, country), GeographicFitType.REGIONAL, 6
        family = re.sub(r"[^A-Za-z0-9]+", "_", row.geography_code).strip("_").upper()
        geography = Geography(
            level=GeographyLevel.CUSTOM,
            code=f"US_{family}",
            name=row.geography_name,
        )
        return geography, (geography, country), GeographicFitType.REGIONAL, 2

    def _component(
        self,
        value: Decimal | str | None,
        unit: str | None,
        denominator: str,
    ) -> tuple[str | None, Decimal | None]:
        if value is None:
            return None, None
        if isinstance(value, str) or not unit:
            raise ValueError(
                "range-valued or unitless components must be excluded before normalize"
            )
        numerator = unit.split("/", 1)[0].strip()
        source_denominator = unit.split("/", 1)[1].strip() if "/" in unit else denominator
        try:
            numerator_scale = self._MASS_TO_KG[numerator]
            canonical_unit, denominator_scale = self._DENOMINATORS[source_denominator]
        except KeyError as error:
            raise ValueError(f"unsupported GHG Protocol unit: {unit}") from error
        return canonical_unit, value * numerator_scale / denominator_scale

    def _provenance(
        self,
        row: GhgProtocolFactorRow,
        raw: RawAssetReference,
        parser_version: str,
        role: ProvenanceRole,
    ) -> FactorProvenance:
        original_unit = {
            ProvenanceRole.CO2: row.co2_unit,
            ProvenanceRole.CH4: row.ch4_unit,
            ProvenanceRole.N2O: row.n2o_unit,
            ProvenanceRole.TOTAL: row.direct_co2e_unit
            or row.co2_unit
            or row.ch4_unit
            or row.n2o_unit,
        }[role]
        return FactorProvenance(
            role=role,
            raw_asset_key=raw.object_key,
            original_url=raw.source_url,
            downloaded_at=raw.downloaded_at,
            file_checksum=raw.sha256,
            original_file=raw.filename,
            parser_version=parser_version,
            mapping_version=self.mapping_version,
            sheet=row.source_sheet,
            table=row.source_table,
            row=row.source_row,
            original_factor_name=row.name,
            original_unit=original_unit,
        )

    @classmethod
    def _derivation(cls, row: GhgProtocolFactorRow) -> dict[str, str]:
        if row.direct_co2e is not None:
            return {"equation": "source_co2e_value", "source_gwp": "source-defined"}
        if row.factor_value_kind == FactorValueKind.CO2_ONLY:
            return {"equation": "source_co2_value"}
        if row.factor_value_kind == FactorValueKind.NON_CO2_CO2E:
            return {
                "equation": "ch4_kg * 28 + n2o_kg * 265",
                "gwp_standard": "IPCC AR5 100-year",
            }
        return {
            "equation": "co2_kg + ch4_kg * 28 + n2o_kg * 265",
            "gwp_standard": "IPCC AR5 100-year",
        }

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
