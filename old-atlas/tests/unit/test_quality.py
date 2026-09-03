from datetime import UTC, datetime
from decimal import Decimal

from atlas.domain.enums import (
    GeographicFitType,
    GeographyDerivation,
    GeographyLevel,
    GeographyRole,
    QualitySeverity,
)
from atlas.domain.models import (
    CanonicalFactor,
    FactorProvenance,
    Geography,
    GeographyAssignment,
)
from atlas.validation import QualityEngine


def factor(**overrides: object) -> CanonicalFactor:
    payload: dict[str, object] = {
        "factor_id": "atlas:defra:diesel:2026:gb",
        "logical_factor_id": "atlas:defra:diesel:gb",
        "source_code": "DEFRA",
        "dataset_id": "defra",
        "dataset_version_id": "defra:2026",
        "name": "Diesel",
        "taxonomy_code": "atlas.energy.diesel",
        "activity_type": "fuel",
        "activity_unit": "l",
        "factor_value": Decimal("2.5123"),
        "factor_unit": "kgCO2e/l",
        "origin_geography": Geography(level=GeographyLevel.COUNTRY, code="GB"),
        "applicable_geographies": (Geography(level=GeographyLevel.COUNTRY, code="GB"),),
        "geography_level": GeographyLevel.COUNTRY,
        "geographic_specificity": 3,
        "geographic_fit_type": GeographicFitType.COUNTRY_SPECIFIC,
        "reference_year": 2026,
        "provenance": FactorProvenance(
            raw_asset_key="sources/defra/2026/abc/original.xlsx",
            original_url="https://example.test/original.xlsx",
            downloaded_at=datetime.now(UTC),
            file_checksum="a" * 64,
            original_file="original.xlsx",
            parser_version="0.1.0",
            mapping_version="0.1.0",
            sheet="Fuels",
            row=143,
        ),
    }
    payload.update(overrides)
    return CanonicalFactor.model_validate(payload)


def test_valid_factor_passes_quality_gate() -> None:
    report = QualityEngine().validate([factor()])

    assert report.checked_records == 1
    assert report.findings == ()
    assert report.requires_review is False


def test_negative_and_unmapped_factor_requires_review() -> None:
    report = QualityEngine().validate(
        [
            factor(
                factor_value=Decimal("-1"),
                taxonomy_code=None,
                origin_geography=None,
                applicable_geographies=(),
            )
        ]
    )

    severities = {finding.severity for finding in report.findings}
    assert QualitySeverity.FAIL in severities
    assert QualitySeverity.REVIEW_REQUIRED in severities
    assert report.requires_review is True


def test_declared_market_role_preserves_unknown_origin_without_false_review() -> None:
    denmark = Geography(level=GeographyLevel.COUNTRY, code="DK", name="Denmark")
    report = QualityEngine().validate(
        [
            factor(
                origin_geography=None,
                applicable_geographies=(denmark,),
                geography_roles=(
                    GeographyAssignment(
                        role=GeographyRole.MARKET,
                        geography=denmark,
                        derivation=GeographyDerivation.SOURCE_DECLARED,
                        source_field="Country",
                        rule_version="test-v1",
                        confidence=1,
                    ),
                ),
            )
        ]
    )

    assert not any(item.rule_code == "geography.origin_missing" for item in report.findings)


def test_semantic_geography_role_must_match_canonical_projection() -> None:
    denmark = Geography(level=GeographyLevel.COUNTRY, code="DK", name="Denmark")
    report = QualityEngine().validate(
        [
            factor(
                geography_roles=(
                    GeographyAssignment(
                        role=GeographyRole.MARKET,
                        geography=denmark,
                        derivation=GeographyDerivation.SOURCE_DECLARED,
                        source_field="Country",
                        rule_version="test-v1",
                        confidence=1,
                    ),
                )
            )
        ]
    )

    assert any(
        item.rule_code == "geography.applicability_role_mismatch"
        and item.severity == QualitySeverity.FAIL
        for item in report.findings
    )
