from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import yaml

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
from atlas.ingestion.errors import PermanentIngestionError
from sources.canada.parser import CanadaFactorRow, CanadaObservationRow, GasCode


class CanadaNormalizer:
    def __init__(self, mappings_path: Path) -> None:
        with mappings_path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"Canada mappings must contain an object: {mappings_path}")
        self.mapping_version = str(payload["version"])
        self.taxonomy: dict[str, str] = {
            str(key): str(value) for key, value in dict(payload["taxonomy"]).items()
        }
        self.provinces: dict[str, str] = {
            str(key): str(value) for key, value in dict(payload["provinces"]).items()
        }

    def normalize(
        self,
        factor_rows: tuple[CanadaFactorRow, ...],
        observation_rows: tuple[CanadaObservationRow, ...],
        *,
        raw: RawAssetReference,
        version: str,
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
                version=version,
                parser_version=parser_version,
            )
            for row in factor_rows
        )
        observations = tuple(
            self._observation(
                row,
                raw=raw,
                version=version,
                parser_version=parser_version,
            )
            for row in observation_rows
        )
        kinds = Counter(factor.factor_value_kind.value for factor in factors)
        fits = Counter(factor.geographic_fit_type.value for factor in factors)
        entities = Counter(item.entity_type.value for item in observations)
        families = Counter(row.table_number.split(".", 1)[0] for row in factor_rows)
        return factors, observations, {
            "normalized_factors": len(factors),
            "source_observations": len(observations),
            "co2_only_factors": kinds["co2_only"],
            "gas_emission_factors": kinds["gas_emission_factor"],
            "co2e_total_factors": kinds["co2e_total"],
            "country_specific_factors": fits["country_specific"],
            "proxy_factors": fits["proxy"],
            "calculation_parameter_observations": entities["calculation_parameter"],
            "reference_value_observations": entities["reference_value"],
            "default_match_eligible": sum(factor.default_match_eligible for factor in factors),
            "excluded_rows": 0,
            **{
                f"table_{family}_factors": count
                for family, count in sorted(families.items())
            },
        }

    def _factor(
        self,
        row: CanadaFactorRow,
        *,
        raw: RawAssetReference,
        version: str,
        parser_version: str,
    ) -> CanonicalFactor:
        factor_value, activity_unit = self._normalize_value(row)
        factor_value_kind = self._value_kind(row.gas)
        geography, applicable, level, fit, specificity = self._geography(row)
        identity = json.dumps(
            [
                row.table_number.split(".", 1)[0],
                row.name,
                row.variant,
                row.gas,
                geography.code,
                activity_unit,
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(identity.encode()).hexdigest()[:20]
        family = row.table_number.split(".", 1)[0]
        logical_id = f"atlas:canada:offset:t{family}:{digest}"
        source_factor_id = (
            f"canada:offset:t{family}:{digest}:{row.valid_from_year}-{row.valid_to_year}"
        )
        return CanonicalFactor(
            factor_id=(
                f"{logical_id}:{row.valid_from_year}-{row.valid_to_year}:v{version}"
            ),
            logical_factor_id=logical_id,
            source_code="CANADA",
            dataset_id="canada-ghg-offset-emission-factors",
            dataset_version_id=f"canada-ghg-offset:v{version}:{raw.sha256[:12]}",
            source_factor_id=source_factor_id,
            name=self._factor_name(row),
            description=(
                "Government of Canada federal offset-system emission factor; use only "
                "for the stated validity period and applicable protocol context."
            ),
            taxonomy_code=self.taxonomy[family],
            source_category=row.category,
            source_subcategory=f"Table {row.table_number}",
            activity_type=self._activity_type(family),
            activity_unit=activity_unit,
            factor_value=factor_value,
            factor_unit=f"kg{row.gas}/{activity_unit}",
            entity_type=EnvironmentalEntityType.EMISSION_FACTOR,
            factor_value_kind=factor_value_kind,
            intended_use=FactorIntendedUse.INVENTORY,
            gases=self._gas_values(row.gas, factor_value),
            origin_geography=geography,
            applicable_geographies=applicable,
            geography_level=level,
            geographic_specificity=specificity,
            geographic_fit_type=fit,
            reference_year=row.reference_year,
            valid_from=date(row.valid_from_year, 1, 1),
            valid_to=date(row.valid_to_year + 1, 1, 1),
            methodology=Methodology(
                scope="scope_2" if family == "5" else "scope_1",
                lifecycle_stage=(
                    "electricity_consumption" if family == "5" else "direct_combustion"
                ),
                system_boundary="Canada federal GHG offset protocol quantification",
                gwp_standard=(
                    None
                    if row.gas in {"CO2", "CO2e"}
                    else "Schedule 3 to the Greenhouse Gas Pollution Pricing Act at event time"
                ),
                methodology="Canada GHG Offset Credit System Version 3.0",
                details={
                    **row.attributes,
                    "table_number": row.table_number,
                    "variant": row.variant,
                    "source_gas": row.gas,
                    "source_value": str(row.value),
                    "source_unit": row.original_unit,
                    "normalization": self._normalization_note(row.original_unit),
                    "valid_from_year": row.valid_from_year,
                    "valid_to_year": row.valid_to_year,
                    "latest_document_required": True,
                    "federal_offset_protocol_context": True,
                },
            ),
            data_quality="ECCC regulatory default; protocol context required",
            provenance=FactorProvenance(
                role=self._provenance_role(row.gas),
                raw_asset_key=raw.object_key,
                original_url=raw.source_url,
                downloaded_at=raw.downloaded_at,
                file_checksum=raw.sha256,
                original_file=raw.filename,
                parser_version=parser_version,
                mapping_version=self.mapping_version,
                table=f"Table {row.table_number}: {row.table_title}",
                row=row.source_row,
                column_number=row.source_column,
                original_factor_name=self._factor_name(row),
                original_unit=row.original_unit,
            ),
            created_at=datetime.now(UTC),
        )

    def _observation(
        self,
        row: CanadaObservationRow,
        *,
        raw: RawAssetReference,
        version: str,
        parser_version: str,
    ) -> SourceObservation:
        identity = json.dumps(
            [row.table_number, row.source_row, row.source_column, row.parameter_code],
            separators=(",", ":"),
        )
        digest = hashlib.sha256(identity.encode()).hexdigest()[:24]
        return SourceObservation(
            observation_id=f"canada:v{version}:offset-parameter:{digest}",
            entity_type=row.entity_type,
            name=row.name,
            value=row.value,
            unit=row.unit,
            reference_year=row.valid_from_year,
            source_category=row.protocol,
            source_subcategory=f"Table {row.table_number}",
            provenance=FactorProvenance(
                role=ProvenanceRole.TOTAL,
                raw_asset_key=raw.object_key,
                original_url=raw.source_url,
                downloaded_at=raw.downloaded_at,
                file_checksum=raw.sha256,
                original_file=raw.filename,
                parser_version=parser_version,
                mapping_version=self.mapping_version,
                table=f"Table {row.table_number}: {row.table_title}",
                row=row.source_row,
                column_number=row.source_column,
                column_name=row.original_column_name,
                original_factor_name=row.name,
                original_unit=row.unit,
            ),
            attributes={
                "parameter_code": row.parameter_code,
                "protocol": row.protocol,
                "valid_from_year": row.valid_from_year,
                "latest_document_required": True,
                "federal_offset_protocol_context": True,
            },
        )

    def _geography(
        self, row: CanadaFactorRow
    ) -> tuple[
        Geography,
        tuple[Geography, ...],
        GeographyLevel,
        GeographicFitType,
        int,
    ]:
        country = Geography(
            level=GeographyLevel.COUNTRY,
            code="CA",
            name="Canada",
        )
        if row.geography_name == "Other provinces and territories":
            geography = Geography(
                level=GeographyLevel.CUSTOM,
                code="CA_OTHER_PROVINCES_TERRITORIES",
                name="Other Canadian provinces and territories",
            )
            return geography, (country,), GeographyLevel.CUSTOM, GeographicFitType.PROXY, 2
        if row.geography_name is not None:
            try:
                code = self.provinces[row.geography_name]
            except KeyError as error:
                raise PermanentIngestionError(
                    f"Canada province mapping is missing: {row.geography_name}"
                ) from error
            geography = Geography(
                level=GeographyLevel.PROVINCE,
                code=code,
                name=row.geography_name,
            )
            return (
                geography,
                (geography, country),
                GeographyLevel.PROVINCE,
                GeographicFitType.COUNTRY_SPECIFIC,
                4,
            )
        return (
            country,
            (country,),
            GeographyLevel.COUNTRY,
            GeographicFitType.COUNTRY_SPECIFIC,
            3,
        )

    @staticmethod
    def _normalize_value(row: CanadaFactorRow) -> tuple[Decimal, str]:
        if row.original_unit.startswith("g"):
            denominator = row.original_unit.split("/", 1)[1]
            activity_unit = "l" if denominator == "L" else denominator
            return row.value / Decimal("1000"), activity_unit
        if row.original_unit == "kgN2O/tCH4":
            return row.value / Decimal("1000"), "kgCH4"
        raise PermanentIngestionError(f"unsupported Canada unit: {row.original_unit}")

    @staticmethod
    def _value_kind(gas: GasCode) -> FactorValueKind:
        if gas == "CO2e":
            return FactorValueKind.CO2E_TOTAL
        if gas == "CO2":
            return FactorValueKind.CO2_ONLY
        return FactorValueKind.GAS_EMISSION_FACTOR

    @staticmethod
    def _gas_values(gas: GasCode, value: Decimal) -> GasValues:
        return {
            "CO2": GasValues(co2=value),
            "CH4": GasValues(ch4=value),
            "N2O": GasValues(n2o=value),
            "CO2e": GasValues(co2e=value),
        }[gas]

    @staticmethod
    def _provenance_role(gas: GasCode) -> ProvenanceRole:
        return {
            "CO2": ProvenanceRole.CO2,
            "CH4": ProvenanceRole.CH4,
            "N2O": ProvenanceRole.N2O,
            "CO2e": ProvenanceRole.TOTAL,
        }[gas]

    @staticmethod
    def _activity_type(family: str) -> str:
        return {
            "1": "stationary-combustion",
            "2": "stationary-combustion",
            "3": "stationary-combustion",
            "4": "stationary-combustion",
            "5": "purchased-electricity",
            "6": "biogas-combustion",
        }[family]

    @staticmethod
    def _factor_name(row: CanadaFactorRow) -> str:
        parts = [row.name]
        if row.variant and row.variant != row.name:
            parts.append(row.variant)
        parts.append(row.gas)
        return " — ".join(parts)

    @staticmethod
    def _normalization_note(unit: str) -> str:
        if unit.startswith("g"):
            return "grams converted to kilograms by dividing by 1000"
        return "kilograms per tonne CH4 converted to kilograms per kilogram CH4"
