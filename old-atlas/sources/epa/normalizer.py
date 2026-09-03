from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import yaml

from atlas.domain.enums import GeographyLevel, ProvenanceRole
from atlas.domain.models import (
    CanonicalFactor,
    FactorProvenance,
    GasValues,
    Geography,
    Methodology,
    RawAssetReference,
)
from atlas.ingestion.errors import PermanentIngestionError
from atlas.units import UnitEngine
from sources.epa.parser import EpaRow

CH4_GWP_AR5 = Decimal("28")
N2O_GWP_AR5 = Decimal("265")
KG_PER_LB = Decimal("0.45359237")
KG_PER_SHORT_TON = Decimal("907.18474")


class EpaNormalizer:
    def __init__(self, mappings_path: Path, unit_engine: UnitEngine | None = None) -> None:
        with mappings_path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        if not isinstance(payload, dict) or not isinstance(payload.get("tables"), dict):
            raise ValueError(f"EPA mappings must contain a tables mapping: {mappings_path}")
        self.mapping_version = str(payload["version"])
        self.table_mappings = {int(key): str(value) for key, value in payload["tables"].items()}
        self.units = unit_engine or UnitEngine()

    def normalize(
        self,
        rows: tuple[EpaRow, ...],
        *,
        raw: RawAssetReference,
        release_year: int,
        parser_version: str,
    ) -> tuple[tuple[CanonicalFactor, ...], dict[str, int]]:
        factors = tuple(
            self._normalize_row(
                row,
                raw=raw,
                release_year=release_year,
                parser_version=parser_version,
            )
            for row in rows
        )
        return factors, {
            "parsed_rows": len(rows),
            "normalized_factors": len(factors),
            "excluded_rows": 0,
            "default_match_eligible": sum(factor.default_match_eligible for factor in factors),
        }

    def _normalize_row(
        self,
        row: EpaRow,
        *,
        raw: RawAssetReference,
        release_year: int,
        parser_version: str,
    ) -> CanonicalFactor:
        try:
            taxonomy_code = self.table_mappings[row.table_number]
        except KeyError as error:
            raise PermanentIngestionError(
                f"EPA table {row.table_number} has no taxonomy mapping"
            ) from error

        co2: Decimal | None = None
        ch4: Decimal | None = None
        n2o: Decimal | None = None
        if row.direct_value is not None:
            factor_value, activity_unit = self._direct_value(row)
        else:
            co2, co2_activity_unit = self._component_value(
                row.co2, row.co2_unit, row.denominator_unit
            )
            ch4, ch4_activity_unit = self._component_value(
                row.ch4, row.ch4_unit, row.denominator_unit
            )
            n2o, n2o_activity_unit = self._component_value(
                row.n2o, row.n2o_unit, row.denominator_unit
            )
            observed_units = {
                unit for unit in (co2_activity_unit, ch4_activity_unit, n2o_activity_unit) if unit
            }
            if len(observed_units) != 1:
                raise PermanentIngestionError(
                    f"EPA gas components normalize to different units at row {row.source_row}"
                )
            activity_unit = next(iter(observed_units))
            factor_value = (
                (co2 or Decimal(0))
                + (ch4 or Decimal(0)) * CH4_GWP_AR5
                + (n2o or Decimal(0)) * N2O_GWP_AR5
            )

        source_factor_id = self._source_factor_id(row)
        logical_id = f"atlas:epa:{source_factor_id.removeprefix('epa:')}"
        provenance = self._provenance(
            row, raw, role=ProvenanceRole.TOTAL, parser_version=parser_version
        )
        components: list[FactorProvenance] = []
        for value, role in (
            (row.co2, ProvenanceRole.CO2),
            (row.ch4, ProvenanceRole.CH4),
            (row.n2o, ProvenanceRole.N2O),
        ):
            if value is not None:
                components.append(
                    self._provenance(row, raw, role=role, parser_version=parser_version)
                )

        return CanonicalFactor(
            factor_id=f"{logical_id}:{release_year}",
            logical_factor_id=logical_id,
            source_code="EPA",
            dataset_id="epa",
            dataset_version_id=f"epa:{release_year}:{raw.sha256[:12]}",
            source_factor_id=source_factor_id,
            name=row.name,
            description=row.description,
            taxonomy_code=taxonomy_code,
            source_category=row.category,
            source_subcategory=f"Table {row.table_number}",
            activity_type=row.activity_type,
            activity_unit=activity_unit,
            factor_value=factor_value,
            factor_unit=f"kgCO2e/{activity_unit}",
            factor_value_kind=row.factor_value_kind,
            intended_use=row.intended_use,
            gases=GasValues(co2=co2, ch4=ch4, n2o=n2o, co2e=factor_value),
            origin_geography=self._geography(row.origin_code),
            applicable_geographies=tuple(
                self._geography(
                    code,
                    str(row.attributes.get("grid_name"))
                    if code == row.attributes.get("grid_code")
                    else None,
                )
                for code in row.applicable_codes
            ),
            geography_level=self._geography_level(row),
            geographic_specificity=self._geographic_specificity(row),
            geographic_fit_type=row.geographic_fit_type,
            reference_year=row.reference_year,
            methodology=Methodology(
                scope=row.scope,
                lifecycle_stage=row.lifecycle_stage,
                system_boundary=row.system_boundary,
                gwp_standard=row.gwp_standard,
                methodology="EPA GHG Emission Factors Hub",
                details={
                    "table_number": row.table_number,
                    "variant": row.variant,
                    "derivation": self._derivation(row),
                    **row.attributes,
                },
            ),
            data_quality="source",
            provenance=provenance,
            component_provenance=tuple(components),
            created_at=datetime.now(UTC),
        )

    def _direct_value(self, row: EpaRow) -> tuple[Decimal, str]:
        if row.direct_value is None:
            raise ValueError("direct value is missing")
        if row.direct_unit == "metric_tonne_co2e":
            # metric tonne CO2e / US short ton material -> kg CO2e / kg material
            return row.direct_value * Decimal("1000") / KG_PER_SHORT_TON, "kg"
        if row.direct_unit == "kg_co2e_per_kg":
            return row.direct_value, "kg"
        raise PermanentIngestionError(
            f"unknown EPA direct unit at row {row.source_row}: {row.direct_unit}"
        )

    def _component_value(
        self, value: Decimal | None, numerator_unit: str | None, denominator_unit: str
    ) -> tuple[Decimal | None, str | None]:
        if value is None:
            return None, None
        numerator_kg = value * self._mass_scale(numerator_unit)
        normalized, activity_unit = self.units.normalize_factor(numerator_kg, denominator_unit)
        return normalized, activity_unit

    @staticmethod
    def _mass_scale(unit: str | None) -> Decimal:
        scales = {"kg": Decimal("1"), "g": Decimal("0.001"), "lb": KG_PER_LB}
        try:
            return scales[unit or ""]
        except KeyError as error:
            raise PermanentIngestionError(f"unknown EPA numerator unit: {unit}") from error

    @staticmethod
    def _source_factor_id(row: EpaRow) -> str:
        identity = f"t{row.table_number}|{row.source_key}|{row.variant}|{row.denominator_unit}"
        digest = hashlib.sha256(identity.encode()).hexdigest()[:12]
        slug = re.sub(r"[^a-z0-9]+", "-", row.source_key.lower()).strip("-")[:120]
        return f"epa:t{row.table_number}:{slug}:{row.variant}:{digest}"

    @staticmethod
    def _geography(code: str, name: str | None = None) -> Geography:
        if code == "GLOBAL":
            return Geography(level=GeographyLevel.GLOBAL, code="GLOBAL", name="Global")
        if code == "US":
            return Geography(level=GeographyLevel.COUNTRY, code="US", name="United States")
        return Geography(level=GeographyLevel.GRID, code=code, name=name or code)

    @staticmethod
    def _geography_level(row: EpaRow) -> GeographyLevel:
        if row.origin_code == "GLOBAL":
            return GeographyLevel.GLOBAL
        if row.attributes.get("grid_code") and row.attributes.get("grid_code") != "US Average":
            return GeographyLevel.GRID
        return GeographyLevel.COUNTRY

    @classmethod
    def _geographic_specificity(cls, row: EpaRow) -> int:
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
        }[cls._geography_level(row)]

    def _provenance(
        self,
        row: EpaRow,
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
            mapping_version=self.mapping_version,
            sheet="Emission Factors Hub",
            table=f"Table {row.table_number}: {row.table_title}",
            row=row.source_row,
            original_factor_name=row.name,
            original_unit=row.original_unit,
        )

    @staticmethod
    def _derivation(row: EpaRow) -> dict[str, str]:
        if row.direct_unit == "metric_tonne_co2e":
            return {
                "equation": "value * 1000 / 907.18474",
                "target_unit": "kgCO2e/kg",
            }
        if row.direct_value is not None:
            return {"equation": "source_value", "target_unit": "kgCO2e/kg"}
        return {
            "equation": "co2_kg + ch4_kg * 28 + n2o_kg * 265",
            "gwp_standard": "IPCC AR5 100-year",
        }
