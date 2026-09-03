from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

import pycountry
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
from sources.cbam.parser import CbamBenchmarkRow, CbamDefaultValueRow


class CbamNormalizer:
    def __init__(self, mappings_path: Path) -> None:
        with mappings_path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"CBAM mappings must contain an object: {mappings_path}")
        self.mapping_version = str(payload["version"])
        self.taxonomy: dict[str, str] = dict(payload["taxonomy"])
        self.country_aliases: dict[str, str] = dict(payload["country_aliases"])
        self.markup_schedule: dict[str, dict[str | int, str]] = dict(
            payload["markup_schedule"]
        )

    def normalize(
        self,
        default_values: tuple[CbamDefaultValueRow, ...],
        benchmarks: tuple[CbamBenchmarkRow, ...],
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
            for row in default_values
        )
        observations = tuple(
            self._observation(
                row,
                raw=raw,
                dataset_version=dataset_version,
                parser_version=parser_version,
            )
            for row in benchmarks
        )
        fits = Counter(factor.geographic_fit_type.value for factor in factors)
        sectors = Counter(row.sector for row in default_values)
        return factors, observations, {
            "normalized_factors": len(factors),
            "source_observations": len(observations),
            "embodied_emission_factors": len(factors),
            "calculation_parameter_observations": len(observations),
            "country_modelled_factors": fits["country_modelled"],
            "proxy_factors": fits["proxy"],
            "default_match_eligible": 0,
            "excluded_rows": 0,
            **{
                f"table_{self._sector_key(sector)}_factors": count
                for sector, count in sectors.items()
            },
        }

    def _factor(
        self,
        row: CbamDefaultValueRow,
        *,
        raw: RawAssetReference,
        dataset_version: str,
        parser_version: str,
    ) -> CanonicalFactor:
        geography, applicable, level, fit, specificity = self._geography(row)
        identity = json.dumps(
            [row.geography_kind, row.geography_name, row.cn_code],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(identity.encode()).hexdigest()[:20]
        source_factor_id = f"cbam:default:{row.cn_code}:{digest}"
        logical_id = f"atlas:{source_factor_id}"
        normalized_sector = self._sector_key(row.sector)
        return CanonicalFactor(
            factor_id=f"{logical_id}:{dataset_version}",
            logical_factor_id=logical_id,
            source_code="CBAM",
            dataset_id="eu-cbam-definitive-default-values",
            dataset_version_id=f"cbam:{dataset_version}:{raw.sha256[:12]}",
            source_factor_id=source_factor_id,
            name=f"{row.description} — CBAM default embedded emissions",
            description=(
                f"EU CBAM definitive base default value for CN/TARIC {row.cn_code}; "
                "the regulatory year markup is not included"
            ),
            taxonomy_code=self.taxonomy[row.sector],
            source_category=row.sector,
            source_subcategory=row.cn_code,
            activity_type=f"cbam_{normalized_sector}_imported_good",
            activity_unit="kg",
            factor_value=row.total_value,
            factor_unit="kgCO2e/kg",
            entity_type=EnvironmentalEntityType.EMBODIED_EMISSION_FACTOR,
            factor_value_kind=FactorValueKind.CO2E_TOTAL,
            intended_use=FactorIntendedUse.CALCULATION_INPUT,
            gases=GasValues(co2e=row.total_value),
            origin_geography=geography,
            applicable_geographies=applicable,
            geography_level=level,
            geographic_specificity=specificity,
            geographic_fit_type=fit,
            valid_from=date(2026, 1, 1),
            reference_year=2026,
            methodology=Methodology(
                lifecycle_stage="embedded_emissions_of_imported_good",
                system_boundary="EU CBAM definitive-regime embedded emissions methodology",
                methodology=(
                    "Commission Implementing Regulation (EU) 2025/2621, "
                    "as corrected by (EU) 2026/1740"
                ),
                details={
                    "cn_or_taric_code": row.cn_code,
                    "default_value_kind": row.geography_kind,
                    "source_total_tco2e_per_tonne": str(row.total_value),
                    "source_direct_tco2e_per_tonne": (
                        str(row.direct_value) if row.direct_value is not None else None
                    ),
                    "source_indirect_tco2e_per_tonne": (
                        str(row.indirect_value) if row.indirect_value is not None else None
                    ),
                    "underlying_production_route": row.production_route,
                    "normalization": "1 tCO2e/tonne equals 1 kgCO2e/kg",
                    "publisher_total_used": True,
                    "markup_not_applied": True,
                    "regulatory_markup_schedule": self.markup_schedule[row.sector],
                    "workbook_is_informational": True,
                    "binding_legal_values": True,
                },
            ),
            data_quality="EU CBAM definitive base; regulatory markup not applied",
            provenance=self._provenance(
                row,
                raw=raw,
                parser_version=parser_version,
                table="default_values",
                original_name=row.description,
                original_unit="tCO2e/tonne of good",
            ),
            created_at=datetime.now(UTC),
        )

    def _observation(
        self,
        row: CbamBenchmarkRow,
        *,
        raw: RawAssetReference,
        dataset_version: str,
        parser_version: str,
    ) -> SourceObservation:
        identity = json.dumps(
            [row.cn_code, row.benchmark_column, row.production_route],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(identity.encode()).hexdigest()[:24]
        column_name = "Column A BMg*" if row.benchmark_column == "A" else "Column B BMg"
        return SourceObservation(
            observation_id=f"cbam:{dataset_version}:benchmark:{digest}",
            entity_type=EnvironmentalEntityType.CALCULATION_PARAMETER,
            name=f"{row.description} — {column_name}",
            value=row.value,
            unit="tCO2e/t",
            reference_year=row.valid_from_year,
            source_category=row.sector,
            source_subcategory=row.cn_code,
            provenance=self._provenance(
                row,
                raw=raw,
                parser_version=parser_version,
                table="benchmarks",
                original_name=row.description,
                original_unit="tCO2e/t",
                column_name=column_name,
            ),
            attributes={
                "cn_code": row.cn_code,
                "benchmark_column": row.benchmark_column,
                "benchmark_kind": row.benchmark_kind,
                "production_route": row.production_route,
                "valid_from_year": row.valid_from_year,
                "valid_to_year": row.valid_to_year,
                "legal_basis": "Commission Implementing Regulation (EU) 2025/2620",
                "workbook_is_informational": True,
            },
        )

    def _geography(
        self, row: CbamDefaultValueRow
    ) -> tuple[
        Geography,
        tuple[Geography, ...],
        GeographyLevel,
        GeographicFitType,
        int,
    ]:
        if row.geography_kind == "country":
            code = self.country_aliases.get(row.geography_name)
            country = pycountry.countries.get(alpha_2=code) if code else None
            if country is None:
                try:
                    country = pycountry.countries.lookup(row.geography_name)
                except LookupError as error:
                    raise ValueError(f"unknown CBAM country: {row.geography_name}") from error
            geography = Geography(
                level=GeographyLevel.COUNTRY,
                code=str(country.alpha_2),
                name=row.geography_name,
            )
            return (
                geography,
                (geography,),
                GeographyLevel.COUNTRY,
                GeographicFitType.COUNTRY_MODELLED,
                3,
            )
        global_geography = Geography(
            level=GeographyLevel.GLOBAL, code="GLOBAL", name="Global"
        )
        code = "CBAM_ANNEX_IV" if row.geography_kind == "annex_iv" else "CBAM_OTHER"
        name = (
            "CBAM Annex IV highest default value"
            if row.geography_kind == "annex_iv"
            else "CBAM other countries and territories default"
        )
        geography = Geography(level=GeographyLevel.CUSTOM, code=code, name=name)
        return (
            geography,
            (global_geography,),
            GeographyLevel.CUSTOM,
            GeographicFitType.PROXY,
            2,
        )

    def _provenance(
        self,
        row: CbamDefaultValueRow | CbamBenchmarkRow,
        *,
        raw: RawAssetReference,
        parser_version: str,
        table: str,
        original_name: str,
        original_unit: str,
        column_name: str | None = None,
    ) -> FactorProvenance:
        return FactorProvenance(
            role=ProvenanceRole.TOTAL,
            raw_asset_key=raw.object_key,
            original_url=row.original_url,
            downloaded_at=raw.downloaded_at,
            file_checksum=row.member_sha256,
            original_file=row.original_file,
            parser_version=parser_version,
            mapping_version=self.mapping_version,
            sheet=row.source_sheet,
            table=table,
            row=row.source_row,
            column_number=(row.source_column if isinstance(row, CbamBenchmarkRow) else 5),
            column_name=column_name,
            original_factor_name=original_name,
            original_unit=original_unit,
        )

    @staticmethod
    def _sector_key(sector: str) -> str:
        return {
            "Cement": "cement",
            "Fertilisers": "fertilisers",
            "Iron and steel": "iron_steel",
            "Iron & Steel": "iron_steel",
            "Aluminium": "aluminium",
            "Hydrogen": "hydrogen",
        }[sector]
