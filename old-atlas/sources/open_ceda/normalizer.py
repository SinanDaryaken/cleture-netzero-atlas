from __future__ import annotations

import re
from datetime import UTC, datetime

import pycountry

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
from sources.open_ceda.parser import OpenCedaFactorRow, OpenCedaParameterRow


class OpenCedaNormalizer:
    mapping_version = "0.1.0"

    def normalize(
        self,
        factor_rows: tuple[OpenCedaFactorRow, ...],
        parameter_rows: tuple[OpenCedaParameterRow, ...],
        *,
        raw: RawAssetReference,
        revision: str,
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
                revision=revision,
                parser_version=parser_version,
            )
            for row in factor_rows
        )
        observations = tuple(
            self._observation(row, raw=raw, parser_version=parser_version)
            for row in parameter_rows
        )
        return factors, observations, {
            "normalized_factors": len(factors),
            "source_observations": len(observations),
            "country_modelled_factors": sum(
                factor.geographic_fit_type == GeographicFitType.COUNTRY_MODELLED
                for factor in factors
            ),
            "regional_fallback_factors": sum(
                factor.geographic_fit_type == GeographicFitType.REGIONAL for factor in factors
            ),
            "proxy_factors": sum(
                factor.geographic_fit_type == GeographicFitType.PROXY for factor in factors
            ),
            "zero_value_factors": sum(factor.factor_value == 0 for factor in factors),
            "default_match_eligible": sum(factor.default_match_eligible for factor in factors),
        }

    def _factor(
        self,
        row: OpenCedaFactorRow,
        *,
        raw: RawAssetReference,
        revision: str,
        parser_version: str,
    ) -> CanonicalFactor:
        origin, applicability, level, fit_type = self._geography(row)
        geography_key = origin.code.lower()
        sector_key = row.sector_code.lower()
        logical_id = f"atlas:open-ceda:spend:{geography_key}:{sector_key}"
        source_factor_id = f"open-ceda:{row.geography_kind}:{geography_key}:{sector_key}"
        activity_unit = f"USD_{row.base_year}_producer_price"
        return CanonicalFactor(
            factor_id=(
                f"{logical_id}:{row.base_year}:ceda-{row.release_year}:{revision[:12]}"
            ),
            logical_factor_id=logical_id,
            source_code="OPEN_CEDA",
            dataset_id="open-ceda-eeio",
            dataset_version_id=f"open-ceda:{row.release_year}:{revision[:12]}",
            source_factor_id=source_factor_id,
            name=f"{row.sector_name} — {row.geography_name}",
            description=(
                "Spend-based total upstream greenhouse-gas intensity from the Open CEDA "
                "multi-regional input-output model."
            ),
            taxonomy_code=f"atlas.spend.economic_sector.{sector_key}",
            source_category="Spend",
            source_subcategory=row.sector_name,
            activity_type="spend",
            activity_unit=activity_unit,
            factor_value=row.value,
            factor_unit=f"kgCO2e/{activity_unit}",
            entity_type=EnvironmentalEntityType.EMISSION_FACTOR,
            factor_value_kind=FactorValueKind.CO2E_TOTAL,
            intended_use=FactorIntendedUse.INVENTORY,
            gases=GasValues(co2e=row.value),
            origin_geography=origin,
            applicable_geographies=applicability,
            geography_level=level,
            geographic_specificity=self._specificity(level),
            geographic_fit_type=fit_type,
            reference_year=row.base_year,
            methodology=Methodology(
                scope="scope_3",
                lifecycle_stage="upstream",
                system_boundary="cradle_to_supplier",
                methodology="Open CEDA multi-regional EEIO",
                details={
                    "release_year": row.release_year,
                    "model_base_year": row.base_year,
                    "price_type": row.price_type,
                    "currency": row.currency,
                    "currency_price_year": row.base_year,
                    "sector_code": row.sector_code,
                    "geography_model": row.geography_kind,
                    "source_matrix": row.source_sheet,
                    "source_column": row.source_column,
                    "calculation_contract": (
                        "activity spend must be converted to model-base-year USD producer price"
                    ),
                },
            ),
            data_quality="modelled_multi_regional_eeio",
            provenance=self._provenance(
                raw=raw,
                parser_version=parser_version,
                sheet=row.source_sheet,
                row=row.source_row,
                column=row.source_column,
                column_name=row.sector_code,
                original_name=f"{row.geography_name} / {row.sector_name}",
                original_unit=row.unit,
            ),
            created_at=datetime.now(UTC),
        )

    def _observation(
        self,
        row: OpenCedaParameterRow,
        *,
        raw: RawAssetReference,
        parser_version: str,
    ) -> SourceObservation:
        dimensions = [row.country_code, row.sector_code, str(row.reference_year or "static")]
        identity = ":".join(self._slug(value) for value in dimensions if value)
        return SourceObservation(
            observation_id=f"open-ceda:{row.parameter_type}:{identity}",
            entity_type=EnvironmentalEntityType.CALCULATION_PARAMETER,
            name=row.name,
            value=row.value,
            unit=row.unit,
            reference_year=row.reference_year,
            source_category="Spend adjustment",
            source_subcategory=row.parameter_type,
            provenance=self._provenance(
                raw=raw,
                parser_version=parser_version,
                sheet=row.source_sheet,
                row=row.source_row,
                column=row.source_column,
                column_name=row.country_code or row.sector_code,
                original_name=row.name,
                original_unit=row.unit,
            ),
            attributes={
                "parameter_type": row.parameter_type,
                "release_year": row.release_year,
                "model_base_year": row.base_year,
                "country_code": row.country_code,
                "country_name": row.country_name,
                "sector_code": row.sector_code,
                "sector_name": row.sector_name,
                "source_column": row.source_column,
            },
        )

    @staticmethod
    def _geography(
        row: OpenCedaFactorRow,
    ) -> tuple[Geography, tuple[Geography, ...], GeographyLevel, GeographicFitType]:
        if row.geography_kind == "regional_average":
            origin = Geography(
                level=GeographyLevel.REGION,
                code=f"OPEN_CEDA_REGION_{row.geography_code}",
                name=row.geography_name,
            )
            applicable = tuple(
                geography
                for code in row.applicable_country_codes
                if (geography := OpenCedaNormalizer._country(code)) is not None
            )
            if not applicable:
                raise PermanentIngestionError(
                    f"Open CEDA region has no ISO applicability: {row.geography_name}"
                )
            return origin, applicable, GeographyLevel.REGION, GeographicFitType.REGIONAL

        if row.geography_code == "ROW":
            origin = Geography(
                level=GeographyLevel.REGION,
                code="OPEN_CEDA_ROW",
                name="Rest of World",
            )
            return (
                origin,
                (Geography(level=GeographyLevel.GLOBAL, code="GLOBAL", name="Global"),),
                GeographyLevel.REGION,
                GeographicFitType.PROXY,
            )

        country = OpenCedaNormalizer._country(row.geography_code)
        if country is None:
            raise PermanentIngestionError(
                f"Open CEDA country code is not ISO 3166-1 alpha-3: {row.geography_code}"
            )
        return (
            country,
            (country,),
            GeographyLevel.COUNTRY,
            GeographicFitType.COUNTRY_MODELLED,
        )

    @staticmethod
    def _country(alpha_3: str) -> Geography | None:
        country = pycountry.countries.get(alpha_3=alpha_3.upper())
        if country is None:
            return None
        return Geography(
            level=GeographyLevel.COUNTRY,
            code=str(country.alpha_2),
            name=str(country.name),
        )

    @classmethod
    def _provenance(
        cls,
        *,
        raw: RawAssetReference,
        parser_version: str,
        sheet: str,
        row: int,
        column: int,
        column_name: str | None,
        original_name: str,
        original_unit: str,
    ) -> FactorProvenance:
        return FactorProvenance(
            role=ProvenanceRole.TOTAL,
            raw_asset_key=raw.object_key,
            original_url=raw.source_url,
            downloaded_at=raw.downloaded_at,
            file_checksum=raw.sha256,
            original_file=raw.filename,
            parser_version=parser_version,
            mapping_version=cls.mapping_version,
            sheet=sheet,
            table=sheet,
            row=row,
            column_number=column,
            column_name=column_name,
            original_factor_name=original_name,
            original_unit=original_unit,
        )

    @staticmethod
    def _specificity(level: GeographyLevel) -> int:
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
        }[level]

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
