from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from atlas.units import ConversionParameter, ConversionResult


class FacilityContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country: str = Field(min_length=2, max_length=64)
    facility_id: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    electricity_connection_level: Literal["distribution", "transmission"] | None = None
    industry_codes: dict[str, str] = Field(default_factory=dict)


class ActivityInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    text: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0)
    unit: str = Field(
        min_length=1,
        max_length=128,
        validation_alias=AliasChoices("unit", "activity_unit"),
    )
    classification_codes: dict[str, str] = Field(default_factory=dict)
    qualifiers: dict[str, str] = Field(default_factory=dict)
    scope3_category: int | None = Field(default=None, ge=1, le=15)
    source_system: str | None = Field(default=None, max_length=128)


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["suggest", "strict"] = "suggest"
    context: str = Field(min_length=1, max_length=64)
    calculation_profile: str = Field(min_length=1, max_length=128)
    language: str | None = Field(default=None, pattern=r"^[a-z]{2}$")
    year: int | None = Field(default=None, ge=1900, le=2200)
    facility_context: FacilityContext
    activity: ActivityInput
    conversion_parameters: tuple[ConversionParameter, ...] = ()
    accept_proxy: bool = False
    limit: int = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def validate_scope3_category_profile(self) -> RecommendationRequest:
        if (
            self.activity.scope3_category is not None
            and "scope3" not in self.calculation_profile.casefold()
        ):
            raise ValueError("scope3_category requires a Scope 3 calculation profile")
        return self


class RecommendationIntent(BaseModel):
    family_code: str
    concept_code: str | None = None
    calculation_role: str
    scope_category: str | None = None
    scope3_category: int | None = Field(default=None, ge=1, le=15)
    activity_basis: str
    qualifiers: dict[str, str] = Field(default_factory=dict)


class RecommendationRank(BaseModel):
    applicability: int
    qualifier: int
    geography: int
    authority: int
    temporal: int
    unit: int
    grade: Literal["A", "B", "C", "D"]
    tier: str


class RecommendationCandidate(BaseModel):
    factor: dict[str, Any]
    applicability: dict[str, Any]
    rank: RecommendationRank
    geography: dict[str, Any]
    conversion: ConversionResult
    lineage: dict[str, Any] = Field(default_factory=dict)
    assumptions: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()


class CalculationPlan(BaseModel):
    original_value: Decimal
    original_unit: str
    normalized_value: Decimal | None = None
    normalized_unit: str
    factor_value: Decimal
    factor_unit: str
    result_value: Decimal | None = None
    result_unit: str | None = None
    formula: str


class RecommendationResponse(BaseModel):
    status: Literal[
        "recommended",
        "needs_input",
        "conversion_parameter_required",
        "proxy_recommended",
        "no_applicable_factor",
    ]
    policy_version: str
    intent: RecommendationIntent
    recommended: RecommendationCandidate | None = None
    alternatives: tuple[RecommendationCandidate, ...] = ()
    assumptions: tuple[str, ...] = ()
    questions: tuple[dict[str, Any], ...] = ()
    calculation: CalculationPlan | None = None
    trace: tuple[dict[str, Any], ...] = ()
    versions: dict[str, str] = Field(default_factory=dict)
