from decimal import Decimal

from atlas.units import (
    ConversionParameter,
    ConversionRequest,
    ConversionStatus,
    UnitEngine,
    UnitMappingStatus,
)


def test_epa_ton_mile_alias_normalizes_as_us_short_ton_mile() -> None:
    value, unit = UnitEngine().normalize_factor(Decimal("1.459972112896"), "ton-mile")

    assert value == Decimal("1")
    assert unit == "tonne.km"


def test_activity_energy_conversion_is_dimensional() -> None:
    result = UnitEngine().convert(
        ConversionRequest(mode="activity", value=Decimal("10"), from_unit="MWh", to_unit="GJ")
    )

    assert result.status == ConversionStatus.EXACT_CONVERSION
    assert result.output_value == Decimal("36")


def test_factor_denominator_conversion_uses_reciprocal_direction() -> None:
    result = UnitEngine().convert(
        ConversionRequest(
            mode="factor",
            value=Decimal("0.5"),
            from_unit="kgCO2e/kWh",
            to_unit="kgCO2e/MWh",
        )
    )

    assert result.status == ConversionStatus.EXACT_CONVERSION
    assert result.output_value == Decimal("500.0")


def test_density_is_required_for_volume_to_mass() -> None:
    engine = UnitEngine()
    missing = engine.convert(
        ConversionRequest(mode="activity", value=Decimal("10"), from_unit="l", to_unit="kg")
    )
    converted = engine.convert(
        ConversionRequest(
            mode="activity",
            value=Decimal("10"),
            from_unit="l",
            to_unit="kg",
            parameters=(
                ConversionParameter(
                    name="density",
                    value=Decimal("800"),
                    unit="kg/m3",
                    source="approved fuel property",
                ),
            ),
        )
    )

    assert missing.status == ConversionStatus.CONDITIONAL_CONVERSION
    assert missing.required_parameters == ("density",)
    assert converted.status == ConversionStatus.CONDITIONAL_CONVERSION
    assert converted.output_value == Decimal("8.000")


def test_calorific_value_parameter_unit_is_scaled_before_conversion() -> None:
    result = UnitEngine().convert(
        ConversionRequest(
            mode="activity",
            value=Decimal("1000"),
            from_unit="m3",
            to_unit="GJ",
            parameters=(
                ConversionParameter(
                    name="calorific_value",
                    value=Decimal("0.0375"),
                    unit="GJ/m3",
                    source="manual",
                ),
            ),
        )
    )

    assert result.status == ConversionStatus.CONDITIONAL_CONVERSION
    assert result.output_value == Decimal("37.5000")


def test_passenger_count_requires_distance_to_create_passenger_kilometres() -> None:
    engine = UnitEngine()
    missing = engine.convert(
        ConversionRequest(
            mode="activity",
            value=Decimal("2"),
            from_unit="passenger",
            to_unit="passenger.km",
        )
    )
    converted = engine.convert(
        ConversionRequest(
            mode="activity",
            value=Decimal("2"),
            from_unit="passenger",
            to_unit="passenger.km",
            parameters=(
                ConversionParameter(
                    name="distance",
                    value=Decimal("500"),
                    unit="km",
                    source="itinerary",
                ),
            ),
        )
    )

    assert missing.status == ConversionStatus.CONDITIONAL_CONVERSION
    assert missing.required_parameters == ("distance",)
    assert missing.output_value is None
    assert converted.status == ConversionStatus.CONDITIONAL_CONVERSION
    assert converted.output_value == Decimal("1000")


def test_wrong_calorific_value_unit_keeps_conversion_blocked() -> None:
    result = UnitEngine().convert(
        ConversionRequest(
            mode="activity",
            value=Decimal("1000"),
            from_unit="m3",
            to_unit="GJ",
            parameters=(
                ConversionParameter(
                    name="calorific_value",
                    value=Decimal("0.0375"),
                    unit="kg/m3",
                    source="manual",
                ),
            ),
        )
    )

    assert result.status == ConversionStatus.CONDITIONAL_CONVERSION
    assert result.output_value is None


def test_unbridged_dimensions_are_incompatible() -> None:
    result = UnitEngine().convert(
        ConversionRequest(mode="activity", value=Decimal("1"), from_unit="l", to_unit="km")
    )

    assert result.status == ConversionStatus.INCOMPATIBLE


def test_source_native_factor_unit_is_mapped_or_explicitly_classified() -> None:
    engine = UnitEngine()

    mapped = engine.classify("kg CH4/head/yr", layer="factor_unit")
    indexed = engine.classify("index_2023=100", layer="source_observation")
    unspecified = engine.classify("source unit not stated", layer="source_observation")

    assert mapped.status == UnitMappingStatus.MAPPED
    assert mapped.canonical_expression == "kgCH4/head.year"
    assert indexed.status == UnitMappingStatus.INDEX
    assert unspecified.status == UnitMappingStatus.SOURCE_UNSPECIFIED


def test_unknown_source_expression_is_never_silently_unparsed() -> None:
    mapping = UnitEngine().classify(
        "publisher-specific technical basis", layer="source_observation"
    )

    assert mapping.status == UnitMappingStatus.SOURCE_NATIVE
    assert mapping.reason_code == "typed_source_native_expression"
