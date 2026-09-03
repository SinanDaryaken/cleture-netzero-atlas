from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any, ClassVar

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
from sources.ipcc.parser import IpccRow

GAS_MARKERS = (
    "co2",
    "ch4",
    "n2o",
    "carbon dioxide",
    "methane",
    "nitrous oxide",
)


class IpccNormalizer:
    CH4_GWP_AR5 = Decimal(28)
    N2O_GWP_AR5 = Decimal(265)
    _MASS_TO_KG: ClassVar[dict[str, Decimal]] = {
        "mg": Decimal("0.000001"),
        "g": Decimal("0.001"),
        "kg": Decimal(1),
        "t": Decimal(1000),
        "tonne": Decimal(1000),
    }
    _DENOMINATORS: ClassVar[dict[str, tuple[str, Decimal]]] = {
        "mj": ("GJ", Decimal("0.001")),
        "gj": ("GJ", Decimal(1)),
        "tj": ("GJ", Decimal(1000)),
        "kwh": ("GJ", Decimal("0.0036")),
        "mwh": ("GJ", Decimal("3.6")),
        "m3": ("m3", Decimal(1)),
        "m³": ("m3", Decimal(1)),
        "l": ("m3", Decimal("0.001")),
        "litre": ("m3", Decimal("0.001")),
        "liter": ("m3", Decimal("0.001")),
        "kg": ("kg", Decimal(1)),
        "t": ("tonne", Decimal(1)),
        "tonne": ("tonne", Decimal(1)),
    }
    _GAS_NAMES: ClassVar[dict[str, str]] = {
        "co2": "co2",
        "carbon dioxide": "co2",
        "ch4": "ch4",
        "methane": "ch4",
        "n2o": "n2o",
        "nitrous oxide": "n2o",
    }

    def __init__(self, mappings_path: Path) -> None:
        with mappings_path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"IPCC mappings must contain an object: {mappings_path}")
        self.mapping_version = str(payload["version"])
        self.sectors_2006 = dict(payload["sectors_2006"])
        self.sectors_1996 = dict(payload["sectors_1996"])

    def normalize(
        self,
        rows: tuple[IpccRow, ...],
        *,
        raw: RawAssetReference,
        dataset_revision: str,
        parser_version: str,
    ) -> tuple[tuple[CanonicalFactor, ...], dict[str, int]]:
        factors: list[CanonicalFactor] = []
        excluded_non_default = 0
        excluded_regional = 0
        excluded_non_numeric = 0
        excluded_missing_unit = 0
        excluded_unmapped_sector = 0
        gas_factors = 0
        calculation_parameters = 0
        eligible_rows: list[IpccRow] = []

        for row in rows:
            if not row.is_default:
                excluded_non_default += 1
                continue
            # Free-text regional conditions must be mapped deliberately. Treating
            # every IPCC default as globally applicable would corrupt coverage.
            if row.regional_conditions:
                excluded_regional += 1
                continue
            if row.value is None:
                excluded_non_numeric += 1
                continue
            if row.unit is None:
                excluded_missing_unit += 1
                continue
            taxonomy_code = self._taxonomy_code(row)
            if taxonomy_code is None:
                excluded_unmapped_sector += 1
                continue
            value_kind, intended_use = self._semantics(row)
            if value_kind == FactorValueKind.CALCULATION_PARAMETER:
                calculation_parameters += 1
            else:
                gas_factors += 1
            factors.append(
                self._factor(
                    row,
                    taxonomy_code=taxonomy_code,
                    raw=raw,
                    dataset_revision=dataset_revision,
                    parser_version=parser_version,
                    value_kind=value_kind,
                    intended_use=intended_use,
                )
            )
            eligible_rows.append(row)

        composite_factors, composite_metrics = self._co2e_composites(
            tuple(eligible_rows),
            raw=raw,
            dataset_revision=dataset_revision,
            parser_version=parser_version,
        )
        factors.extend(composite_factors)

        excluded = (
            excluded_non_default
            + excluded_regional
            + excluded_non_numeric
            + excluded_missing_unit
            + excluded_unmapped_sector
        )
        return tuple(factors), {
            "parsed_rows": len(rows),
            "normalized_factors": len(factors),
            "gas_emission_factors": gas_factors,
            "calculation_parameters": calculation_parameters,
            "excluded_non_default": excluded_non_default,
            "excluded_unmapped_geography": excluded_regional,
            "excluded_non_numeric": excluded_non_numeric,
            "excluded_missing_unit": excluded_missing_unit,
            "excluded_unmapped_sector": excluded_unmapped_sector,
            "excluded_rows": excluded,
            "canonical_co2e_totals": len(composite_factors),
            "composite_groups_incomplete": composite_metrics["incomplete"],
            "composite_groups_ambiguous": composite_metrics["ambiguous"],
            "composite_groups_unsupported_unit": composite_metrics["unsupported_unit"],
            "default_match_eligible": len(composite_factors),
        }

    def _co2e_composites(
        self,
        rows: tuple[IpccRow, ...],
        *,
        raw: RawAssetReference,
        dataset_revision: str,
        parser_version: str,
    ) -> tuple[tuple[CanonicalFactor, ...], dict[str, int]]:
        groups: dict[tuple[str, ...], dict[str, list[IpccRow]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for row in rows:
            key = self._composite_key(row)
            gas = self._gas_code(row.gas)
            if key is not None and gas is not None:
                groups[key][gas].append(row)

        composites: list[CanonicalFactor] = []
        metrics = {"incomplete": 0, "ambiguous": 0, "unsupported_unit": 0}
        for components in groups.values():
            if set(components) != {"co2", "ch4", "n2o"}:
                metrics["incomplete"] += 1
                continue
            if any(len(components[gas]) != 1 for gas in ("co2", "ch4", "n2o")):
                metrics["ambiguous"] += 1
                continue
            rows_by_gas = {gas: components[gas][0] for gas in ("co2", "ch4", "n2o")}
            normalized = {gas: self._normalized_component(row) for gas, row in rows_by_gas.items()}
            if any(value is None for value in normalized.values()):
                metrics["unsupported_unit"] += 1
                continue
            units = {value[0] for value in normalized.values() if value is not None}
            if len(units) != 1:
                metrics["unsupported_unit"] += 1
                continue
            canonical_unit = units.pop()
            values = {gas: value[1] for gas, value in normalized.items() if value is not None}
            composites.append(
                self._composite_factor(
                    rows_by_gas,
                    values=values,
                    canonical_unit=canonical_unit,
                    raw=raw,
                    dataset_revision=dataset_revision,
                    parser_version=parser_version,
                )
            )
        return tuple(composites), metrics

    @classmethod
    def _composite_key(cls, row: IpccRow) -> tuple[str, ...] | None:
        category = row.category_2006 or row.category_1996 or ""
        fuel = row.fuel_2006 or row.fuel_1996 or ""
        if not re.match(r"\s*1\.A(?:\.|\s|$)", category, flags=re.IGNORECASE) or not fuel:
            return None
        if cls._gas_code(row.gas) is None:
            return None
        return tuple(
            cls._group_text(value)
            for value in (
                "2006" if row.category_2006 else "1996",
                category,
                fuel,
                row.parameter_type,
                row.technology,
                row.conditions,
                row.abatement,
                row.carbon_pool,
            )
        )

    @staticmethod
    def _group_text(value: str | None) -> str:
        return " ".join((value or "").casefold().split())

    @classmethod
    def _gas_code(cls, value: str | None) -> str | None:
        return cls._GAS_NAMES.get(cls._group_text(value))

    @classmethod
    def _normalized_component(cls, row: IpccRow) -> tuple[str, Decimal] | None:
        if row.value is None or row.unit is None or "/" not in row.unit:
            return None
        numerator, denominator = (part.strip() for part in row.unit.split("/", 1))
        numerator_token = cls._group_text(numerator).split(" ", 1)[0]
        denominator_token = cls._group_text(denominator)
        denominator_token = re.sub(r"\s+(fuel|feed|dry matter)$", "", denominator_token)
        try:
            numerator_scale = cls._MASS_TO_KG[numerator_token]
            canonical_unit, denominator_scale = cls._DENOMINATORS[denominator_token]
        except KeyError:
            return None
        return canonical_unit, row.value * numerator_scale / denominator_scale

    def _composite_factor(
        self,
        rows: dict[str, IpccRow],
        *,
        values: dict[str, Decimal],
        canonical_unit: str,
        raw: RawAssetReference,
        dataset_revision: str,
        parser_version: str,
    ) -> CanonicalFactor:
        representative = rows["co2"]
        fuel = representative.fuel_2006 or representative.fuel_1996 or "Fuel"
        category = representative.category_2006 or representative.category_1996 or "1.A"
        component_ids = tuple(sorted(row.ef_id for row in rows.values()))
        identity = sha256("|".join(component_ids).encode()).hexdigest()[:20]
        logical_id = f"atlas:ipcc:efdb:co2e:{identity}"
        co2e = values["co2"] + values["ch4"] * self.CH4_GWP_AR5 + values["n2o"] * self.N2O_GWP_AR5
        global_geography = Geography(
            level=GeographyLevel.GLOBAL,
            code="GLOBAL",
            name="Global",
        )
        component_provenance = tuple(
            self._component_provenance(rows[gas], raw=raw, parser_version=parser_version, role=role)
            for gas, role in (
                ("co2", ProvenanceRole.CO2),
                ("ch4", ProvenanceRole.CH4),
                ("n2o", ProvenanceRole.N2O),
            )
        )
        return CanonicalFactor(
            factor_id=f"{logical_id}:{dataset_revision[:12]}",
            logical_factor_id=logical_id,
            source_code="IPCC",
            dataset_id="ipcc-efdb",
            dataset_version_id=f"ipcc-efdb:{dataset_revision[:12]}",
            source_factor_id=f"ipcc:efdb:co2e:{identity}",
            name=f"IPCC AR5 CO₂e combustion factor — {fuel} — {category}",
            description=(
                "Atlas-derived canonical total from the exact IPCC EFDB default "
                "CO₂, CH₄ and N₂O component group."
            ),
            taxonomy_code="atlas.energy",
            source_category=category,
            source_subcategory=representative.parameter_type,
            activity_type="energy",
            activity_unit=canonical_unit,
            factor_value=co2e,
            factor_unit=f"kgCO2e/{canonical_unit}",
            factor_value_kind=FactorValueKind.CO2E_TOTAL,
            intended_use=FactorIntendedUse.INVENTORY,
            gases=GasValues(co2=values["co2"], ch4=values["ch4"], n2o=values["n2o"], co2e=co2e),
            origin_geography=global_geography,
            applicable_geographies=(global_geography,),
            geography_level=GeographyLevel.GLOBAL,
            geographic_specificity=0,
            geographic_fit_type=GeographicFitType.GLOBAL,
            methodology=Methodology(
                scope="scope_1",
                lifecycle_stage="direct_combustion",
                system_boundary="direct fuel combustion",
                gwp_standard="IPCC AR5 GWP100",
                methodology="Atlas derivation from IPCC EFDB default component factors",
                details={
                    "derivation": {
                        "equation": "co2_kg + ch4_kg * 28 + n2o_kg * 265",
                        "gwp_standard": "IPCC AR5 100-year",
                        "source_reported_total": False,
                    },
                    "component_efdb_ids": {gas: row.ef_id for gas, row in rows.items()},
                    "component_source_units": {gas: row.unit for gas, row in rows.items()},
                    "fuel": fuel,
                    "category": category,
                },
            ),
            data_quality="IPCC default components; Atlas AR5 derivation",
            provenance=FactorProvenance(
                role=ProvenanceRole.TOTAL,
                raw_asset_key=raw.object_key,
                original_url=raw.source_url,
                downloaded_at=raw.downloaded_at,
                file_checksum=raw.sha256,
                original_file=raw.filename,
                parser_version=parser_version,
                mapping_version=self.mapping_version,
                sheet="Sheet1",
                table="IPCC EFDB export",
                original_factor_name=f"Atlas composite of EFDB {', '.join(component_ids)}",
                original_unit=None,
            ),
            component_provenance=component_provenance,
            created_at=datetime.now(UTC),
        )

    def _component_provenance(
        self,
        row: IpccRow,
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
            sheet="Sheet1",
            table="IPCC EFDB export",
            row=row.source_row,
            original_factor_name=self._name(row),
            original_unit=row.unit,
        )

    def _factor(
        self,
        row: IpccRow,
        *,
        taxonomy_code: str,
        raw: RawAssetReference,
        dataset_revision: str,
        parser_version: str,
        value_kind: FactorValueKind,
        intended_use: FactorIntendedUse,
    ) -> CanonicalFactor:
        if row.value is None or row.unit is None:
            raise ValueError("IPCC factor requires a numeric value and unit")
        source_factor_id = f"ipcc:efdb:{row.ef_id}"
        logical_id = f"atlas:ipcc:efdb:{row.ef_id}"
        global_geography = Geography(
            level=GeographyLevel.GLOBAL,
            code="GLOBAL",
            name="Global",
        )
        return CanonicalFactor(
            factor_id=f"{logical_id}:{dataset_revision[:12]}",
            logical_factor_id=logical_id,
            source_code="IPCC",
            dataset_id="ipcc-efdb",
            dataset_version_id=f"ipcc-efdb:{dataset_revision[:12]}",
            source_factor_id=source_factor_id,
            name=self._name(row),
            description=row.description,
            taxonomy_code=taxonomy_code,
            source_category=row.category_2006 or row.category_1996,
            source_subcategory=row.parameter_type,
            activity_type=taxonomy_code.split(".")[1],
            activity_unit=self._activity_unit(row, value_kind),
            factor_value=row.value,
            factor_unit=row.unit,
            factor_value_kind=value_kind,
            intended_use=intended_use,
            gases=GasValues(),
            origin_geography=global_geography,
            applicable_geographies=(global_geography,),
            geography_level=GeographyLevel.GLOBAL,
            geographic_specificity=0,
            geographic_fit_type=GeographicFitType.GLOBAL,
            methodology=Methodology(
                system_boundary="inventory_model",
                methodology="IPCC EFDB default data",
                details=self._methodology_details(row),
            ),
            data_quality="ipcc_default",
            provenance=FactorProvenance(
                role=ProvenanceRole.TOTAL,
                raw_asset_key=raw.object_key,
                original_url=raw.source_url,
                downloaded_at=raw.downloaded_at,
                file_checksum=raw.sha256,
                original_file=raw.filename,
                parser_version=parser_version,
                mapping_version=self.mapping_version,
                sheet="Sheet1",
                table="IPCC EFDB export",
                row=row.source_row,
                original_factor_name=self._name(row),
                original_unit=row.unit,
            ),
            created_at=datetime.now(UTC),
        )

    def _taxonomy_code(self, row: IpccRow) -> str | None:
        category = row.category_2006 or row.category_1996
        if not category:
            return None
        match = re.match(r"\s*([1-6])(?:\.|\s|$)", category)
        if match is None:
            return None
        mappings = self.sectors_2006 if row.category_2006 else self.sectors_1996
        return mappings.get(match.group(1))

    @staticmethod
    def _semantics(row: IpccRow) -> tuple[FactorValueKind, FactorIntendedUse]:
        unit = (row.unit or "").lower()
        description = (row.description or "").lower()
        is_emission_factor = "emission factor" in description or (
            "/" in unit and any(marker in unit for marker in GAS_MARKERS)
        )
        if not is_emission_factor:
            return FactorValueKind.CALCULATION_PARAMETER, FactorIntendedUse.CALCULATION_INPUT
        if (row.gas or "").strip().upper() == "CARBON DIOXIDE":
            return FactorValueKind.CO2_ONLY, FactorIntendedUse.INVENTORY
        return FactorValueKind.GAS_EMISSION_FACTOR, FactorIntendedUse.INVENTORY

    @staticmethod
    def _activity_unit(row: IpccRow, value_kind: FactorValueKind) -> str:
        unit = row.unit or ""
        if value_kind == FactorValueKind.CALCULATION_PARAMETER:
            if unit.lower() in {"%", "fraction", "dimensionless", "no dimension"}:
                return "dimensionless"
            return "calculation_input"
        _, separator, denominator = unit.partition("/")
        return denominator.strip() if separator and denominator.strip() else "source_activity"

    @staticmethod
    def _name(row: IpccRow) -> str:
        qualifiers = [row.fuel_2006 or row.fuel_1996, row.carbon_pool]
        suffix = " / ".join(value for value in qualifiers if value)
        base = row.description or row.gas or row.parameter_type or f"EFDB {row.ef_id}"
        return f"{base} / {suffix}" if suffix else base

    @staticmethod
    def _methodology_details(row: IpccRow) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "efdb_id": row.ef_id,
                "parameter_role": (
                    "emission_factor"
                    if IpccNormalizer._semantics(row)[1] == FactorIntendedUse.INVENTORY
                    else "calculation_input"
                ),
                "type_of_parameter": row.parameter_type,
                "gas": row.gas,
                "fuel_1996": row.fuel_1996,
                "fuel_2006": row.fuel_2006,
                "carbon_pool": row.carbon_pool,
                "technology": row.technology,
                "conditions": row.conditions,
                "abatement": row.abatement,
                "other_properties": row.other_properties,
                "equation": row.equation,
                "worksheet": row.worksheet,
                "technical_reference": row.technical_reference,
                "source_of_data": row.source_of_data,
                "data_provider": row.data_provider,
                "raw_value": row.raw_value,
            }.items()
            if value is not None
        }
