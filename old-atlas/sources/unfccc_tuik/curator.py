from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

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
from sources.unfccc_tuik.parser import UnfcccTuikRow

AR4_GWP = {"CO2": Decimal(1), "CH4": Decimal(25), "N2O": Decimal(298)}
AR5_GWP = {"CO2": Decimal(1), "CH4": Decimal(28), "N2O": Decimal(265)}
CO2_PER_C = Decimal(44) / Decimal(12)
N2O_PER_N = Decimal(44) / Decimal(28)


@dataclass(frozen=True)
class NormalizedComponent:
    row: UnfcccTuikRow
    gas: str
    value: Decimal
    activity_unit: str
    conversion: str


class UnfcccTuikCurator:
    """Build matching-safe CO2e factors from source-native CRT/CRF observations."""

    def __init__(self, sectors: dict[str, str], mapping_version: str) -> None:
        self.sectors = sectors
        self.mapping_version = mapping_version

    def curate(
        self,
        rows: tuple[UnfcccTuikRow, ...],
        *,
        raw: RawAssetReference,
        dataset_revision: str,
        parser_version: str,
    ) -> tuple[tuple[CanonicalFactor, ...], dict[str, int]]:
        groups: dict[tuple[int, str, int, str], list[UnfcccTuikRow]] = defaultdict(list)
        for row in rows:
            if row.entity_type == EnvironmentalEntityType.IMPLIED_EMISSION_FACTOR:
                groups[
                    (row.reference_year, row.source_sheet, row.source_row, row.category_path)
                ].append(row)

        factors: list[CanonicalFactor] = []
        excluded: Counter[str] = Counter()
        for group_rows in groups.values():
            components: list[NormalizedComponent] = []
            for row in group_rows:
                component, reason = self._normalize_component(row)
                if component is None:
                    excluded[reason or "unsupported_component"] += 1
                    components = []
                    break
                components.append(component)
            if not components:
                continue
            activity_units = {component.activity_unit for component in components}
            gases = [component.gas for component in components]
            if len(activity_units) != 1:
                excluded["incompatible_component_units"] += 1
                continue
            if len(gases) != len(set(gases)):
                excluded["duplicate_gas_component"] += 1
                continue
            factors.append(
                self._factor(
                    components,
                    raw=raw,
                    dataset_revision=dataset_revision,
                    parser_version=parser_version,
                )
            )

        return tuple(factors), {
            "curation_candidate_groups": len(groups),
            "curated_factors": len(factors),
            "curation_excluded_groups": sum(excluded.values()),
            **{f"curation_excluded_{key}": value for key, value in excluded.items()},
        }

    def _factor(
        self,
        components: list[NormalizedComponent],
        *,
        raw: RawAssetReference,
        dataset_revision: str,
        parser_version: str,
    ) -> CanonicalFactor:
        first = components[0].row
        activity_unit = components[0].activity_unit
        gwp_standard, gwp = (
            ("AR4", AR4_GWP) if first.submission_year <= 2023 else ("AR5", AR5_GWP)
        )
        gas_values = {component.gas: component.value for component in components}
        co2e = sum(
            (component.value * gwp[component.gas] for component in components),
            start=Decimal(0),
        )
        identity = "|".join(
            (
                self._identity_text(first.source_sheet),
                self._identity_text(first.category_path),
                str(first.source_row),
                activity_unit,
                "national_inventory_implied_factor",
            )
        )
        identity_hash = hashlib.sha256(identity.encode()).hexdigest()[:20]
        logical_id = f"atlas:unfccc-tuik:curated:{identity_hash}"
        source_factor_id = f"unfccc-tuik:curated:{identity_hash}:{first.reference_year}"
        taxonomy_code = self._taxonomy_code(first)
        tr = Geography(level=GeographyLevel.COUNTRY, code="TR", name="Türkiye")
        component_provenance = tuple(
            self._provenance(
                component.row,
                raw=raw,
                parser_version=parser_version,
                role=ProvenanceRole(component.gas.lower()),
            )
            for component in components
        )
        return CanonicalFactor(
            factor_id=(
                f"{logical_id}:{first.reference_year}:{first.submission_year}:"
                f"{dataset_revision[:12]}"
            ),
            logical_factor_id=logical_id,
            source_code="UNFCCC_TUIK",
            dataset_id="unfccc-tuik-national-inventory",
            dataset_version_id=(
                f"unfccc-tuik:{first.submission_year}:{dataset_revision[:12]}"
            ),
            source_factor_id=source_factor_id,
            name=first.category_path,
            description=(
                "Türkiye national inventory implied emission factor curated from "
                f"UNFCCC {first.schema_family.upper()} gas components."
            ),
            taxonomy_code=taxonomy_code,
            source_category=first.category_path,
            source_subcategory=first.source_sheet,
            activity_type=taxonomy_code.removeprefix("atlas.").split(".", maxsplit=1)[0],
            activity_unit=activity_unit,
            factor_value=co2e,
            factor_unit=f"kgCO2e/{activity_unit}",
            entity_type=EnvironmentalEntityType.EMISSION_FACTOR,
            factor_value_kind=FactorValueKind.CO2E_TOTAL,
            intended_use=FactorIntendedUse.INVENTORY,
            gases=GasValues(
                co2=gas_values.get("CO2"),
                ch4=gas_values.get("CH4"),
                n2o=gas_values.get("N2O"),
                co2e=co2e,
            ),
            origin_geography=tr,
            applicable_geographies=(tr,),
            geography_level=GeographyLevel.COUNTRY,
            geographic_specificity=3,
            geographic_fit_type=GeographicFitType.COUNTRY_SPECIFIC,
            valid_from=date(first.reference_year, 1, 1),
            valid_to=date(first.reference_year, 12, 31),
            reference_year=first.reference_year,
            methodology=Methodology(
                system_boundary="national_inventory_implied_factor",
                gwp_standard=gwp_standard,
                methodology=f"UNFCCC {first.schema_family.upper()} source-derived curation",
                details={
                    "submission_year": first.submission_year,
                    "submission_status": first.submission_status,
                    "inventory_reference_year": first.reference_year,
                    "source_sheet": first.source_sheet,
                    "source_row": first.source_row,
                    "component_conversions": [
                        {
                            "gas": component.gas,
                            "source_value": str(component.row.value),
                            "source_unit": component.row.unit,
                            "normalized_value": str(component.value),
                            "normalized_unit": f"kg{component.gas}/{activity_unit}",
                            "conversion": component.conversion,
                        }
                        for component in components
                    ],
                },
            ),
            data_quality=f"source_derived_{gwp_standard.lower()}",
            provenance=self._provenance(
                first,
                raw=raw,
                parser_version=parser_version,
                role=ProvenanceRole.TOTAL,
            ),
            component_provenance=component_provenance,
            created_at=datetime.now(UTC),
        )

    def _normalize_component(
        self, row: UnfcccTuikRow
    ) -> tuple[NormalizedComponent | None, str | None]:
        unit = self._unit_text(row.unit)
        label = self._unit_text(row.column_label)
        gas = row.gas
        value = row.value

        if unit == "t/tj":
            return self._component(row, gas, value, "GJ", "t/TJ -> kg/GJ")
        if unit == "kg/tj":
            return self._component(
                row, gas, value / Decimal(1000), "GJ", "kg/TJ -> kg/GJ"
            )
        if unit == "t c/tj":
            return self._component(
                row,
                "CO2",
                value * CO2_PER_C,
                "GJ",
                "tC/TJ -> kgCO2/GJ (44/12)",
            )
        if unit == "t/t":
            return self._component(row, gas, value, "kg", "t/t -> kg/kg")
        if unit == "kg/t":
            return self._component(
                row, gas, value / Decimal(1000), "kg", "kg/t -> kg/kg"
            )
        if "t co2-c" in unit and unit.endswith("/t"):
            return self._component(
                row,
                "CO2",
                value * CO2_PER_C,
                "kg",
                "tCO2-C/t -> kgCO2/kg (44/12)",
            )
        if unit == "kg ch4/head/yr":
            return self._component(row, "CH4", value, "head.year", "identity")
        if unit == "g/m2":
            return self._component(
                row, gas, value / Decimal(1000), "m2", "g/m2 -> kg/m2"
            )
        if "kg n2o-n/kg n" in unit or "kg n2o-n/kg n" in label:
            return self._component(
                row,
                "N2O",
                value * N2O_PER_N,
                "kg_nitrogen",
                "kgN2O-N/kgN -> kgN2O/kgN (44/28)",
            )
        if unit == "kg/t dm":
            return self._component(
                row,
                gas,
                value / Decimal(1000),
                "kg_dry_matter",
                "kg/t dry matter -> kg/kg dry matter",
            )
        if "kg n2o-n/ha" in unit:
            return self._component(
                row,
                "N2O",
                value * N2O_PER_N,
                "ha",
                "kgN2O-N/ha -> kgN2O/ha (44/28)",
            )
        if unit == "t/t waste":
            return self._component(row, gas, value, "kg_waste", "t/t waste -> kg/kg waste")
        if unit == "kg/t waste":
            return self._component(
                row,
                gas,
                value / Decimal(1000),
                "kg_waste",
                "kg/t waste -> kg/kg waste",
            )
        if unit.startswith("kg/unit"):
            resolved = self._activity_unit(row.activity_unit)
            if resolved is None:
                return None, "missing_activity_unit"
            activity_unit, denominator_scale = resolved
            return self._component(
                row,
                gas,
                value / denominator_scale,
                activity_unit,
                f"kg/source unit -> kg/{activity_unit}",
            )
        if unit == "t/activity data unit":
            resolved = self._activity_unit(row.activity_unit)
            if resolved is None:
                return None, "missing_activity_unit"
            activity_unit, denominator_scale = resolved
            return self._component(
                row,
                gas,
                value * Decimal(1000) / denominator_scale,
                activity_unit,
                f"t/source unit -> kg/{activity_unit}",
            )
        return None, "unsupported_unit"

    @staticmethod
    def _component(
        row: UnfcccTuikRow,
        gas: str | None,
        value: Decimal,
        activity_unit: str,
        conversion: str,
    ) -> tuple[NormalizedComponent | None, str | None]:
        if gas not in {"CO2", "CH4", "N2O"}:
            return None, "unsupported_gas"
        return NormalizedComponent(row, gas, value, activity_unit, conversion), None

    @classmethod
    def _activity_unit(cls, source: str | None) -> tuple[str, Decimal] | None:
        if source is None:
            return None
        normalized = cls._unit_text(source).replace(" ", "")
        match = re.fullmatch(r"10\^(\d+)(.+)", normalized)
        scale = Decimal(1)
        if match:
            scale = Decimal(10) ** int(match.group(1))
            normalized = match.group(2)
        aliases = {
            "m^3": "m3",
            "m3": "m3",
            "ha": "ha",
            "t": "kg",
            "head": "head",
        }
        canonical = aliases.get(normalized)
        if canonical is None:
            return None
        if normalized == "t":
            scale *= Decimal(1000)
        return canonical, scale

    def _taxonomy_code(self, row: UnfcccTuikRow) -> str:
        match = re.match(r"Table([1-5])", row.source_sheet, re.IGNORECASE)
        if match is None:
            match = re.match(r"\s*([1-5])(?:\.|\s)", row.category_path)
        return self.sectors[match.group(1) if match is not None else "1"]

    def _provenance(
        self,
        row: UnfcccTuikRow,
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
            file_checksum=row.member_sha256,
            original_file=row.member_filename,
            parser_version=parser_version,
            mapping_version=self.mapping_version,
            sheet=row.source_sheet,
            table=row.schema_family,
            row=row.source_row,
            original_factor_name=f"{row.category_path} / {row.column_label}",
            original_unit=row.unit,
        )

    @staticmethod
    def _unit_text(value: str) -> str:
        return " ".join(
            value.casefold().replace("\u2013", "-").replace("\u00b2", "2").split()
        )

    @classmethod
    def _identity_text(cls, value: str) -> str:
        without_footnotes = re.sub(r"\(\d+(?:,\d+)*\)", "", value)
        return " ".join(without_footnotes.casefold().split())
