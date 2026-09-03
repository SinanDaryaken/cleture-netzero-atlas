from collections.abc import Iterable

from atlas.domain.enums import (
    EnvironmentalEntityType,
    FactorIntendedUse,
    FactorValueKind,
    GeographicFitType,
    GeographyLevel,
    GeographyRole,
    QualitySeverity,
)
from atlas.domain.models import CanonicalFactor, QualityFinding, QualityReport


class QualityEngine:
    """Small v0 rule set; database-defined rules can be layered on this contract later."""

    def validate(self, factors: Iterable[CanonicalFactor]) -> QualityReport:
        records = tuple(factors)
        findings: list[QualityFinding] = []
        seen_factor_ids: set[str] = set()

        for factor in records:
            if (
                factor.factor_value < 0
                and factor.entity_type
                in {
                    EnvironmentalEntityType.EMISSION_FACTOR,
                    EnvironmentalEntityType.IMPLIED_EMISSION_FACTOR,
                    EnvironmentalEntityType.EMBODIED_EMISSION_FACTOR,
                }
                and factor.factor_value_kind != FactorValueKind.CALCULATION_PARAMETER
                and factor.intended_use != FactorIntendedUse.AVOIDED_EMISSIONS
            ):
                findings.append(
                    QualityFinding(
                        rule_code="factor.negative_value",
                        severity=QualitySeverity.FAIL,
                        message="factor value cannot be negative",
                        factor_id=factor.factor_id,
                    )
                )
            if factor.factor_id in seen_factor_ids:
                findings.append(
                    QualityFinding(
                        rule_code="factor.duplicate_id",
                        severity=QualitySeverity.FAIL,
                        message="factor_id is duplicated in the normalized batch",
                        factor_id=factor.factor_id,
                    )
                )
            seen_factor_ids.add(factor.factor_id)

            if factor.taxonomy_code is None:
                findings.append(
                    QualityFinding(
                        rule_code="taxonomy.unmapped",
                        severity=QualitySeverity.REVIEW_REQUIRED,
                        message="source category has no approved Atlas taxonomy mapping",
                        factor_id=factor.factor_id,
                    )
                )
            if factor.origin_geography is None and not factor.geography_roles:
                findings.append(
                    QualityFinding(
                        rule_code="geography.origin_missing",
                        severity=QualitySeverity.REVIEW_REQUIRED,
                        message="factor origin geography is missing",
                        factor_id=factor.factor_id,
                    )
                )
            role_keys: set[tuple[GeographyRole, str]] = set()
            applicable_codes = {geography.code for geography in factor.applicable_geographies}
            for assignment in factor.geography_roles:
                key = (assignment.role, assignment.geography.code)
                if key in role_keys:
                    findings.append(
                        QualityFinding(
                            rule_code="geography.role_duplicate",
                            severity=QualitySeverity.FAIL,
                            message="semantic geography role is duplicated",
                            factor_id=factor.factor_id,
                        )
                    )
                role_keys.add(key)
                if assignment.role == GeographyRole.PRODUCTION_ORIGIN and (
                    factor.origin_geography is None
                    or factor.origin_geography.code != assignment.geography.code
                ):
                    findings.append(
                        QualityFinding(
                            rule_code="geography.origin_role_mismatch",
                            severity=QualitySeverity.FAIL,
                            message="production origin role does not match origin geography",
                            factor_id=factor.factor_id,
                        )
                    )
                if (
                    assignment.role
                    in {GeographyRole.MARKET, GeographyRole.CALCULATION_APPLICABILITY}
                    and assignment.geography.code not in applicable_codes
                ):
                    findings.append(
                        QualityFinding(
                            rule_code="geography.applicability_role_mismatch",
                            severity=QualitySeverity.FAIL,
                            message=(
                                "market/applicability role is absent from applicable geographies"
                            ),
                            factor_id=factor.factor_id,
                        )
                    )
            if not factor.applicable_geographies:
                findings.append(
                    QualityFinding(
                        rule_code="geography.applicability_missing",
                        severity=QualitySeverity.REVIEW_REQUIRED,
                        message="factor applicable geography is missing",
                        factor_id=factor.factor_id,
                    )
                )
            expected_specificity = {
                GeographyLevel.GLOBAL: 0,
                GeographyLevel.CONTINENT: 1,
                GeographyLevel.REGION: 2,
                GeographyLevel.COUNTRY: 3,
                GeographyLevel.STATE: 4,
                GeographyLevel.PROVINCE: 4,
                GeographyLevel.CITY: 5,
                GeographyLevel.GRID: 6,
                GeographyLevel.CUSTOM: 2,
            }[factor.geography_level]
            if factor.geographic_specificity != expected_specificity:
                findings.append(
                    QualityFinding(
                        rule_code="geography.specificity_mismatch",
                        severity=QualitySeverity.FAIL,
                        message="geographic specificity does not match geography level",
                        factor_id=factor.factor_id,
                    )
                )
            if factor.geographic_fit_type in {
                GeographicFitType.COUNTRY_SPECIFIC,
                GeographicFitType.COUNTRY_MODELLED,
            } and factor.geography_level not in {
                GeographyLevel.COUNTRY,
                GeographyLevel.STATE,
                GeographyLevel.PROVINCE,
                GeographyLevel.CITY,
                GeographyLevel.GRID,
            }:
                findings.append(
                    QualityFinding(
                        rule_code="geography.country_fit_level_mismatch",
                        severity=QualitySeverity.REVIEW_REQUIRED,
                        message="country fit requires country or subnational geography level",
                        factor_id=factor.factor_id,
                    )
                )
            if (
                factor.geographic_fit_type == GeographicFitType.GLOBAL
                and factor.geography_level != GeographyLevel.GLOBAL
            ):
                findings.append(
                    QualityFinding(
                        rule_code="geography.global_fit_level_mismatch",
                        severity=QualitySeverity.REVIEW_REQUIRED,
                        message="global fit requires global geography level",
                        factor_id=factor.factor_id,
                    )
                )
            if factor.reference_year is None:
                findings.append(
                    QualityFinding(
                        rule_code="year.missing",
                        severity=QualitySeverity.WARNING,
                        message="factor reference year is missing",
                        factor_id=factor.factor_id,
                    )
                )

        return QualityReport(checked_records=len(records), findings=tuple(findings))
