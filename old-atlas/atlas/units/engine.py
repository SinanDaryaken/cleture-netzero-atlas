from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml

from atlas.ingestion.errors import PermanentIngestionError
from atlas.units.models import (
    ConversionMode,
    ConversionParameter,
    ConversionRequest,
    ConversionResult,
    ConversionStatus,
    UnitDefinition,
    UnitExpression,
    UnitMapping,
    UnitMappingStatus,
)


class UnitEngine:
    """Versioned dimensional registry for activity and factor conversions."""

    def __init__(self, registry_path: Path | None = None) -> None:
        path = registry_path or Path(__file__).with_name("registry.yaml")
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.version = str(payload["version"])
        self._definitions: dict[str, UnitDefinition] = {}
        self._aliases: dict[str, str] = {}
        for item in payload["units"]:
            definition = UnitDefinition.model_validate(item)
            self._definitions[definition.code] = definition
            for alias in (definition.code, *definition.aliases):
                self._aliases[self._normalize_alias(alias)] = definition.code
        self._bridges: dict[tuple[str, str], str] = {
            (str(item["from_dimension"]), str(item["to_dimension"])): str(item["parameter"])
            for item in payload.get("conditional_bridges", [])
        }
        # Keep the already-published ingestion normalization contract stable.
        self._legacy_denominators: dict[str, tuple[str, Decimal]] = {
            "GJ": ("GJ", Decimal("1")),
            "MMBtu": ("GJ", Decimal("1.05505585262")),
            "mmBtu": ("GJ", Decimal("1.05505585262")),
            "Room per night": ("room.night", Decimal("1")),
            "cubic metres": ("m3", Decimal("1")),
            "scf": ("m3", Decimal("0.028316846592")),
            "gallon": ("l", Decimal("3.785411784")),
            "kWh": ("kWh", Decimal("1")),
            "MWh": ("kWh", Decimal("1000")),
            "kWh (Gross CV)": ("kWh_gross_cv", Decimal("1")),
            "kWh (Net CV)": ("kWh_net_cv", Decimal("1")),
            "kg": ("kg", Decimal("1")),
            "km": ("km", Decimal("1")),
            "litres": ("l", Decimal("1")),
            "miles": ("km", Decimal("1.609344")),
            "vehicle-mile": ("vehicle.km", Decimal("1.609344")),
            "passenger-mile": ("passenger.km", Decimal("1.609344")),
            "short ton-mile": ("tonne.km", Decimal("1.459972112896")),
            "ton-mile": ("tonne.km", Decimal("1.459972112896")),
            "short ton": ("tonne", Decimal("0.90718474")),
            "million litres": ("l", Decimal("1000000")),
            "passenger.km": ("passenger.km", Decimal("1")),
            "per FTE Working Hour": ("fte.hour", Decimal("1")),
            "tonne.km": ("tonne.km", Decimal("1")),
            "tonnes": ("tonne", Decimal("1")),
        }

    def definitions(self) -> tuple[UnitDefinition, ...]:
        return tuple(sorted(self._definitions.values(), key=lambda item: item.code))

    def definition(self, code_or_alias: str) -> UnitDefinition:
        normalized = self._normalize_alias(code_or_alias)
        try:
            return self._definitions[self._aliases[normalized]]
        except KeyError as error:
            raise LookupError(f"unknown unit: {code_or_alias}") from error

    def parse(self, expression: str) -> UnitExpression:
        original = self._normalize_expression(expression)
        try:
            return UnitExpression(original=original, numerator=self.definition(original))
        except LookupError:
            pass
        if "/" not in original:
            return UnitExpression(original=original, numerator=self.definition(original))
        numerator_text, denominator_text = original.split("/", 1)
        match = re.fullmatch(r"\s*(?:(\d+(?:\.\d+)?)\s*[* ]\s*)?(.+?)\s*", denominator_text)
        if match is None:
            raise LookupError(f"invalid unit expression: {expression}")
        return UnitExpression(
            original=original,
            numerator=self.definition(numerator_text.strip()),
            denominator=self.definition(match.group(2).strip()),
            denominator_quantity=Decimal(match.group(1) or "1"),
        )

    def classify(self, expression: str, *, layer: str) -> UnitMapping:
        """Return an exhaustive mapping disposition without discarding source text."""

        raw = expression.strip()
        normalized = self._normalize_expression(raw)
        try:
            parsed = self.parse(normalized)
        except LookupError:
            status, reason = self._non_convertible_disposition(normalized, layer=layer)
            return UnitMapping(
                raw_expression=raw,
                normalized_expression=normalized,
                status=status,
                reason_code=reason,
            )
        return UnitMapping(
            raw_expression=raw,
            normalized_expression=normalized,
            status=UnitMappingStatus.MAPPED,
            canonical_expression=parsed.canonical_code,
            numerator_code=parsed.numerator.code,
            denominator_code=parsed.denominator.code if parsed.denominator else None,
            denominator_quantity=(
                parsed.denominator_quantity if parsed.denominator is not None else None
            ),
            reason_code="canonical_registry_match",
        )

    def convert(self, request: ConversionRequest) -> ConversionResult:
        try:
            source = self.parse(request.from_unit)
            target = self.parse(request.to_unit)
        except LookupError as error:
            return self._incompatible(request, str(error))
        if request.mode == ConversionMode.ACTIVITY:
            if source.denominator is not None or target.denominator is not None:
                return self._incompatible(request, "activity conversion requires simple units")
            return self._convert_activity(request, source, target)
        if source.denominator is None or target.denominator is None:
            return self._incompatible(request, "factor conversion requires numerator/denominator")
        return self._convert_factor(request, source, target)

    def normalize_factor(self, value: Decimal, source_unit: str) -> tuple[Decimal, str]:
        try:
            canonical, denominator_scale = self._legacy_denominators[source_unit]
        except KeyError as error:
            raise PermanentIngestionError(f"unknown source unit: {source_unit}") from error
        return value / denominator_scale, canonical

    def _convert_activity(
        self, request: ConversionRequest, source: UnitExpression, target: UnitExpression
    ) -> ConversionResult:
        outcome = self._activity_multiplier(
            source.numerator,
            target.numerator,
            request.parameters,
            request.calculation_date,
        )
        if isinstance(outcome, tuple):
            multiplier, parameters_used = outcome
            return self._result(request, source, target, multiplier, parameters_used)
        if outcome:
            return self._conditional(request, source, target, outcome)
        return self._incompatible(
            request, "unit dimensions or semantic qualifiers are incompatible"
        )

    def _convert_factor(
        self, request: ConversionRequest, source: UnitExpression, target: UnitExpression
    ) -> ConversionResult:
        numerator = self._exact_multiplier(source.numerator, target.numerator)
        if numerator is None:
            return self._incompatible(request, "factor numerator units are incompatible")
        assert source.denominator is not None and target.denominator is not None
        denominator = self._activity_multiplier(
            source.denominator,
            target.denominator,
            request.parameters,
            request.calculation_date,
        )
        if isinstance(denominator, str):
            return self._conditional(request, source, target, denominator)
        if denominator is None:
            return self._incompatible(request, "factor denominator units are incompatible")
        activity_multiplier, parameters_used = denominator
        multiplier = (
            numerator
            * target.denominator_quantity
            / source.denominator_quantity
            / activity_multiplier
        )
        return self._result(request, source, target, multiplier, parameters_used)

    def _activity_multiplier(
        self,
        source: UnitDefinition,
        target: UnitDefinition,
        parameters: tuple[ConversionParameter, ...],
        calculation_date: date | None,
    ) -> tuple[Decimal, tuple[ConversionParameter, ...]] | str | None:
        exact = self._exact_multiplier(source, target)
        if exact is not None:
            return exact, ()
        parameter_name = self._bridges.get((source.dimension, target.dimension))
        if parameter_name is None:
            return None
        parameter = next((item for item in parameters if item.name == parameter_name), None)
        if parameter is None:
            return parameter_name
        if calculation_date is not None:
            if parameter.valid_from and calculation_date < parameter.valid_from:
                return parameter_name
            if parameter.valid_to and calculation_date > parameter.valid_to:
                return parameter_name
        bridge = self._bridge_multiplier(source, target, parameter)
        if bridge is None:
            return parameter_name
        return bridge, (parameter,)

    @staticmethod
    def _exact_multiplier(source: UnitDefinition, target: UnitDefinition) -> Decimal | None:
        if source.dimension != target.dimension or source.qualifiers != target.qualifiers:
            return None
        if source.offset_to_base != 0 or target.offset_to_base != 0:
            return None
        return source.scale_to_base / target.scale_to_base

    def _bridge_multiplier(
        self,
        source: UnitDefinition,
        target: UnitDefinition,
        parameter: ConversionParameter,
    ) -> Decimal | None:
        pair = (source.dimension, target.dimension)
        ratio: UnitExpression | None = None
        if pair in {
            ("volume", "mass"),
            ("mass", "volume"),
            ("volume", "energy"),
            ("mass", "energy"),
        }:
            try:
                parsed = self.parse(parameter.unit)
            except LookupError:
                return None
            ratio = parsed if parsed.denominator is not None else None
        if pair == ("volume", "mass"):
            if not self._is_ratio(ratio, "mass", "volume"):
                return None
            assert ratio is not None
            density = self._ratio_to_base(parameter.value, ratio)
            return source.scale_to_base * density / target.scale_to_base
        if pair == ("mass", "volume"):
            if not self._is_ratio(ratio, "mass", "volume"):
                return None
            assert ratio is not None
            density = self._ratio_to_base(parameter.value, ratio)
            return source.scale_to_base / density / target.scale_to_base
        if pair in {("volume", "energy"), ("mass", "energy")}:
            if not self._is_ratio(ratio, "energy", source.dimension):
                return None
            assert ratio is not None
            calorific_value = self._ratio_to_base(parameter.value, ratio)
            return source.scale_to_base * calorific_value / target.scale_to_base
        value = parameter.value
        if pair == ("distance", "transport_work"):
            return source.scale_to_base * value * Decimal("1000") / target.scale_to_base
        if pair == ("distance", "passenger_distance"):
            return source.scale_to_base * value / target.scale_to_base
        if pair == ("passenger_count", "passenger_distance"):
            try:
                distance = self.parse(parameter.unit)
            except LookupError:
                return None
            if distance.denominator is not None or distance.numerator.dimension != "distance":
                return None
            return (
                source.scale_to_base
                * value
                * distance.numerator.scale_to_base
                / target.scale_to_base
            )
        if pair == ("currency", "currency"):
            return value
        return None

    @staticmethod
    def _is_ratio(
        expression: UnitExpression | None,
        numerator_dimension: str,
        denominator_dimension: str,
    ) -> bool:
        return bool(
            expression
            and expression.denominator
            and expression.numerator.dimension == numerator_dimension
            and expression.denominator.dimension == denominator_dimension
        )

    @staticmethod
    def _ratio_to_base(value: Decimal, expression: UnitExpression) -> Decimal:
        assert expression.denominator is not None
        return (
            value
            * expression.numerator.scale_to_base
            / expression.denominator.scale_to_base
            / expression.denominator_quantity
        )

    def _result(
        self,
        request: ConversionRequest,
        source: UnitExpression,
        target: UnitExpression,
        multiplier: Decimal,
        parameters_used: tuple[ConversionParameter, ...],
    ) -> ConversionResult:
        return ConversionResult(
            status=(
                ConversionStatus.CONDITIONAL_CONVERSION
                if parameters_used
                else ConversionStatus.EXACT_CONVERSION
            ),
            mode=request.mode,
            input_value=request.value,
            output_value=request.value * multiplier,
            from_expression=source.canonical_code,
            to_expression=target.canonical_code,
            multiplier=multiplier,
            formula="output = input * multiplier",
            parameters_used=parameters_used,
            registry_version=self.version,
        )

    def _conditional(
        self,
        request: ConversionRequest,
        source: UnitExpression,
        target: UnitExpression,
        parameter: str,
    ) -> ConversionResult:
        return ConversionResult(
            status=ConversionStatus.CONDITIONAL_CONVERSION,
            mode=request.mode,
            input_value=request.value,
            from_expression=source.canonical_code,
            to_expression=target.canonical_code,
            required_parameters=(parameter,),
            warnings=(f"conversion requires a provenance-bearing {parameter} parameter",),
            registry_version=self.version,
        )

    def _incompatible(self, request: ConversionRequest, warning: str) -> ConversionResult:
        return ConversionResult(
            status=ConversionStatus.INCOMPATIBLE,
            mode=request.mode,
            input_value=request.value,
            from_expression=request.from_unit,
            to_expression=request.to_unit,
            warnings=(warning,),
            registry_version=self.version,
        )

    @staticmethod
    def _normalize_alias(value: str) -> str:
        return " ".join(value.strip().casefold().split())

    @staticmethod
    def _normalize_expression(value: str) -> str:
        normalized = value.strip()
        replacements = {
            "CO₂": "CO2",
            "CH₄": "CH4",
            "N₂O": "N2O",
            "\u2013": "-",
            "\u2212": "-",
            "³": "3",
            "²": "2",
            "µ": "u",
        }
        for source, target in replacements.items():
            normalized = normalized.replace(source, target)
        return " ".join(normalized.split())

    @staticmethod
    def _non_convertible_disposition(
        expression: str, *, layer: str
    ) -> tuple[UnitMappingStatus, str]:
        normalized = expression.casefold()
        if not normalized or any(
            marker in normalized
            for marker in (
                "source_unit_unspecified",
                "source unit unspecified",
                "source unit not stated",
                "unit not stated",
                "unit unspecified",
            )
        ):
            return UnitMappingStatus.SOURCE_UNSPECIFIED, "publisher_did_not_state_unit"
        if normalized in {"dimensionless", "no dimension", "fraction", "%", "percent"}:
            return UnitMappingStatus.DIMENSIONLESS, "dimensionless_quantity"
        if normalized.startswith("index_") or normalized.startswith("index "):
            return UnitMappingStatus.INDEX, "indexed_quantity"
        if normalized == "ratio" or "fraction of" in normalized or "% of" in normalized:
            return UnitMappingStatus.RATIO, "ratio_or_share"
        if normalized in {"calculation_input", "source_activity"}:
            return UnitMappingStatus.CALCULATION_PARAMETER, "abstract_calculation_input"
        if layer == "source_observation" and len(expression) > 255:
            return UnitMappingStatus.SOURCE_NATIVE, "publisher_note_in_unit_cell"
        return UnitMappingStatus.SOURCE_NATIVE, "typed_source_native_expression"
