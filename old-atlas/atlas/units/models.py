from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConversionMode(StrEnum):
    ACTIVITY = "activity"
    FACTOR = "factor"


class ConversionStatus(StrEnum):
    EXACT_CONVERSION = "exact_conversion"
    CONDITIONAL_CONVERSION = "conditional_conversion"
    INCOMPATIBLE = "incompatible"


class UnitMappingStatus(StrEnum):
    """Exhaustive disposition for a source-native unit expression."""

    MAPPED = "mapped"
    DIMENSIONLESS = "dimensionless"
    RATIO = "ratio"
    INDEX = "index"
    CALCULATION_PARAMETER = "calculation_parameter"
    SOURCE_UNSPECIFIED = "source_unspecified"
    SOURCE_NATIVE = "source_native"


class UnitDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=128)
    dimension: str = Field(min_length=1, max_length=128)
    scale_to_base: Decimal = Field(gt=0)
    offset_to_base: Decimal = Decimal("0")
    aliases: tuple[str, ...] = ()
    ucum_code: str | None = None
    qualifiers: tuple[str, ...] = ()


class UnitExpression(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    original: str
    numerator: UnitDefinition
    denominator: UnitDefinition | None = None
    denominator_quantity: Decimal = Field(default=Decimal("1"), gt=0)

    @property
    def canonical_code(self) -> str:
        if self.denominator is None:
            return self.numerator.code
        quantity = "" if self.denominator_quantity == 1 else f"{self.denominator_quantity}*"
        return f"{self.numerator.code}/{quantity}{self.denominator.code}"


class UnitMapping(BaseModel):
    """Canonical mapping or an explicit, non-convertible source-native classification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_expression: str
    normalized_expression: str
    status: UnitMappingStatus
    canonical_expression: str | None = None
    numerator_code: str | None = None
    denominator_code: str | None = None
    denominator_quantity: Decimal | None = None
    reason_code: str

    @property
    def convertible(self) -> bool:
        return self.status == UnitMappingStatus.MAPPED


class ConversionParameter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=64)
    value: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=128)
    source: str = Field(min_length=1, max_length=512)
    valid_from: date | None = None
    valid_to: date | None = None

    @model_validator(mode="after")
    def validate_validity(self) -> ConversionParameter:
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("conversion parameter valid_from must not exceed valid_to")
        return self


class ConversionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: ConversionMode
    value: Decimal
    from_unit: str = Field(min_length=1, max_length=255)
    to_unit: str = Field(min_length=1, max_length=255)
    parameters: tuple[ConversionParameter, ...] = ()
    calculation_date: date | None = None


class ConversionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ConversionStatus
    mode: ConversionMode
    input_value: Decimal
    output_value: Decimal | None = None
    from_expression: str
    to_expression: str
    multiplier: Decimal | None = None
    formula: str | None = None
    required_parameters: tuple[str, ...] = ()
    parameters_used: tuple[ConversionParameter, ...] = ()
    warnings: tuple[str, ...] = ()
    registry_version: str
