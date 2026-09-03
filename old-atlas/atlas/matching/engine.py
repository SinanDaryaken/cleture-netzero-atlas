from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, ClassVar

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from atlas.geography import GeographicCoverageEngine, GeographicEvaluation
from atlas.semantics import HARD_REJECTION_REASONS, EligibilityDecision, SemanticRegistry
from atlas.units import ConversionParameter, ConversionRequest, ConversionStatus, UnitEngine


class MatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    activity: str = Field(min_length=1, max_length=255)
    country: str = Field(min_length=2, max_length=64)
    context: str | None = Field(default=None, min_length=1, max_length=64)
    calculation_profile: str = Field(min_length=1, max_length=128)
    year: int | None = Field(default=None, ge=1900, le=2200)
    quantity: Decimal | None = Field(default=None, gt=0)
    activity_unit: str | None = Field(
        default=None,
        max_length=128,
        validation_alias=AliasChoices("unit", "activity_unit"),
        serialization_alias="unit",
    )
    boundary: str | None = Field(default=None, max_length=128)
    methodology: str | None = Field(default=None, max_length=255)
    conversion_parameters: tuple[ConversionParameter, ...] = ()
    allow_geographic_proxy: bool = False


class MatchScore(BaseModel):
    activity: int
    unit: int
    geography: int
    year: int
    boundary: int
    methodology: int
    source_quality: int
    data_quality: int
    final: float


class RankedMatch(BaseModel):
    factor: dict[str, Any]
    confidence: float
    score: MatchScore
    geographic_coverage: GeographicEvaluation
    eligibility: EligibilityDecision
    unit_conversion_status: ConversionStatus | None = None
    warnings: tuple[str, ...] = ()


class MatchResponse(BaseModel):
    selected: RankedMatch
    alternatives: tuple[RankedMatch, ...] = ()
    rejected: tuple[RankedMatch, ...] = ()
    concept_resolution: dict[str, Any] | None = None


class ResolveResponse(BaseModel):
    selected: RankedMatch
    decision: str = "resolved"


class FactorMatchingEngine:
    WEIGHTS: ClassVar[dict[str, float]] = {
        "activity": 0.30,
        "unit": 0.15,
        "geography": 0.20,
        "year": 0.10,
        "boundary": 0.10,
        "methodology": 0.05,
        "source_quality": 0.05,
        "data_quality": 0.05,
    }

    def __init__(
        self,
        geography: GeographicCoverageEngine,
        semantics: SemanticRegistry | None = None,
        units: UnitEngine | None = None,
    ) -> None:
        self.geography = geography
        self.semantics = semantics or SemanticRegistry()
        self.units = units or UnitEngine()

    def match(self, request: MatchRequest, candidates: list[dict[str, Any]]) -> MatchResponse:
        all_ranked = [self._rank(request, candidate) for candidate in candidates]
        ranked = [
            item
            for item in all_ranked
            if item.geographic_coverage.eligible and item.eligibility.calculation_eligible
        ]
        if not ranked:
            raise LookupError("no_calculation_eligible_candidate")
        ranked.sort(
            key=lambda item: (
                item.geographic_coverage.fallback_rank,
                -item.score.final,
                item.factor["factor_id"],
            )
        )
        rejected = [
            item
            for item in all_ranked
            if item not in ranked
            and not (set(item.eligibility.reason_codes) & HARD_REJECTION_REASONS)
        ]
        rejected.sort(key=lambda item: (-item.score.final, item.factor["factor_id"]))
        resolution = self.semantics.resolve_concept(request.activity)
        alternatives = list(ranked[1:4])
        visible = [ranked[0], *alternatives]
        if any(self._is_ipcc_derived_ghg(item.factor) for item in visible) and not any(
            item.factor.get("source_code") == "IPCC" for item in visible
        ):
            primary = next(
                (item for item in ranked[1:] if item.factor.get("source_code") == "IPCC"),
                None,
            )
            if primary is not None:
                if len(alternatives) < 3:
                    alternatives.append(primary)
                else:
                    alternatives[-1] = primary
        return MatchResponse(
            selected=ranked[0],
            alternatives=tuple(alternatives),
            rejected=tuple(rejected[:20]),
            concept_resolution=resolution.model_dump(mode="json"),
        )

    def resolve(self, request: MatchRequest, candidates: list[dict[str, Any]]) -> ResolveResponse:
        response = self.match(request, candidates)
        return ResolveResponse(selected=response.selected)

    def _rank(self, request: MatchRequest, factor: dict[str, Any]) -> RankedMatch:
        eligibility = self.semantics.evaluate(request.calculation_profile, factor)
        geographic = self.geography.evaluate(request.country, factor)
        if request.allow_geographic_proxy and not geographic.eligible:
            geographic = geographic.model_copy(
                update={
                    "geographic_score": min(35, geographic.geographic_score),
                    "fallback_rank": 10_000,
                    "fallback_used": True,
                    "eligible": True,
                    "warning": (
                        f"No {request.country.upper()}, regional or global factor is available; "
                        f"using {geographic.factor_geography} as an explicit geographic proxy"
                    ),
                }
            )
        unit_score, unit_status, unit_resolved = self._unit_score(
            request.activity_unit, factor, request.conversion_parameters
        )
        unit_reasons: list[str] = []
        profile = self.semantics.profile(request.calculation_profile)
        if unit_status == ConversionStatus.INCOMPATIBLE:
            unit_reasons.append("unit_incompatible")
        if (
            unit_status == ConversionStatus.CONDITIONAL_CONVERSION
            and not profile.allow_conditional_conversion
        ):
            unit_reasons.append("unit_conditional_denied")
        if unit_reasons:
            eligibility = EligibilityDecision(
                search_eligible=eligibility.search_eligible,
                calculation_eligible=False,
                reason_codes=tuple((*eligibility.reason_codes, *unit_reasons)),
                profile=eligibility.profile,
                policy_version=eligibility.policy_version,
            )
        activity_score = self._activity_score(request.activity, factor)
        if activity_score < 60:
            eligibility = EligibilityDecision(
                search_eligible=eligibility.search_eligible,
                calculation_eligible=False,
                reason_codes=tuple((*eligibility.reason_codes, "activity_concept_mismatch")),
                profile=eligibility.profile,
                policy_version=eligibility.policy_version,
            )
        scores = {
            "activity": activity_score,
            "unit": unit_score,
            "geography": geographic.geographic_score,
            "year": self._year_score(
                request.year,
                factor.get("reference_year"),
                factor.get("data_quality"),
            ),
            "boundary": self._text_dimension_score(
                request.boundary,
                (factor.get("methodology") or {}).get("system_boundary"),
            ),
            "methodology": self._text_dimension_score(
                request.methodology,
                (factor.get("methodology") or {}).get("methodology"),
            ),
            "source_quality": self._source_quality_score(factor.get("source_health")),
            "data_quality": self._data_quality_score(factor.get("data_quality")),
        }
        final = round(sum(scores[name] * weight for name, weight in self.WEIGHTS.items()), 2)
        warnings = [geographic.warning] if geographic.warning else []
        warnings.extend(eligibility.reason_codes)
        if unit_status == ConversionStatus.CONDITIONAL_CONVERSION:
            warnings.append("unit_conditional")
            if not unit_resolved:
                warnings.append("unit_parameter_required")
        elif unit_status == ConversionStatus.INCOMPATIBLE:
            warnings.append("unit_incompatible")
        score = MatchScore(**scores, final=final)
        return RankedMatch(
            factor=factor,
            confidence=round(final / 100, 4),
            score=score,
            geographic_coverage=geographic,
            eligibility=eligibility,
            unit_conversion_status=unit_status,
            warnings=tuple(warnings),
        )

    def _activity_score(self, activity: str, factor: dict[str, Any]) -> int:
        needle = FactorMatchingEngine._normalize(activity)
        taxonomy = FactorMatchingEngine._normalize(str(factor.get("taxonomy_code", "")))
        activity_type = FactorMatchingEngine._normalize(str(factor.get("activity_type", "")))
        name = FactorMatchingEngine._normalize(str(factor.get("name", "")))
        concept = FactorMatchingEngine._normalize(str(factor.get("concept_code", "")))
        details = (factor.get("methodology") or {}).get("details") or {}
        application = FactorMatchingEngine._normalize(str(details.get("application", "")))
        resolution = self.semantics.resolve_concept(activity)
        if resolution.concept_code == "energy.natural_gas" and (
            ("electricity" in taxonomy and "natural gas" not in taxonomy)
            or "natural gas liquids" in name
            or "natural gasoline" in name
            or activity_type == "spend"
            or (
                activity_type == "transport energy"
                and ("from natural gas" in name or "from natural gas" in application)
                and not name.startswith("natural gas")
            )
        ):
            return 40
        resolved_concept = self._normalize(resolution.concept_code or "")
        if (
            needle in {taxonomy, concept}
            or taxonomy.endswith(f" {needle}")
            or (resolved_concept and resolved_concept in taxonomy)
            or (resolved_concept and resolved_concept == concept)
        ):
            return 100
        if needle == activity_type:
            return 90
        haystack = set(name.split())
        for term in resolution.search_terms:
            normalized_term = self._normalize(term)
            if normalized_term and set(normalized_term.split()).issubset(haystack):
                return 100 if resolution.confidence >= 0.85 else 80
        tokens = set(needle.split())
        if tokens and tokens.issubset(set(name.split())):
            return 80
        return 60

    def _unit_score(
        self,
        requested: str | None,
        factor: dict[str, Any],
        parameters: tuple[ConversionParameter, ...],
    ) -> tuple[int, ConversionStatus | None, bool]:
        if requested is None:
            return 100, None, True
        actual = str(factor.get("activity_unit", ""))
        result = self.units.convert(
            ConversionRequest(
                mode="activity",
                value=Decimal("1"),
                from_unit=requested,
                to_unit=actual,
                parameters=parameters,
            )
        )
        if result.status == ConversionStatus.EXACT_CONVERSION:
            return 100, result.status, True
        if result.status == ConversionStatus.CONDITIONAL_CONVERSION:
            return 60, result.status, result.output_value is not None
        return 0, result.status, False

    @staticmethod
    def _year_score(
        requested: int | None, factor_year: int | None, data_quality: str | None = None
    ) -> int:
        if requested is None:
            return 100
        if factor_year is None:
            return 50
        difference = abs(requested - factor_year)
        if difference <= 2:
            return 100
        normalized_quality = FactorMatchingEngine._normalize(data_quality or "")
        if difference <= 5 and "official annual" in normalized_quality:
            return 100
        if difference == 3:
            return 85
        return max(0, 70 - difference * 5)

    @staticmethod
    def _text_dimension_score(requested: str | None, actual: str | None) -> int:
        if requested is None:
            return 100
        if actual is None:
            return 50
        return 100 if requested.casefold() == actual.casefold() else 25

    @staticmethod
    def _source_quality_score(health: str | None) -> int:
        return {
            "healthy": 100,
            "warning": 75,
            "stale": 50,
            "failed": 0,
            "disabled": 0,
        }.get(health or "", 50)

    @staticmethod
    def _data_quality_score(quality: str | None) -> int:
        normalized = FactorMatchingEngine._normalize(quality or "")
        if "official" in normalized or normalized in {"source", "source derived"}:
            return 100
        if "source derived" in normalized:
            return 95
        if "default" in normalized:
            return 85
        if "modelled" in normalized or "modeled" in normalized:
            return 60
        return 75 if normalized else 50

    @staticmethod
    def _is_ipcc_derived_ghg(factor: dict[str, Any]) -> bool:
        if factor.get("source_code") != "GHG_PROTOCOL":
            return False
        details = (factor.get("methodology") or {}).get("details") or {}
        return "ipcc" in str(details.get("original_source", "")).casefold()

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())
