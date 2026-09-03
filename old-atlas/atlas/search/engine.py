from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from atlas.geography import GeographicCoverageEngine, GeographicEvaluation
from atlas.semantics import HARD_REJECTION_REASONS, EligibilityDecision, SemanticRegistry
from atlas.units import ConversionParameter, ConversionRequest, ConversionStatus, UnitEngine


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    context: str = Field(min_length=1, max_length=64)
    calculation_profile: str | None = Field(default=None, max_length=128)
    language: str | None = Field(default=None, pattern=r"^[a-z]{2}$")
    geography: str | None = Field(default=None, min_length=2, max_length=64)
    year: int | None = Field(default=None, ge=1900, le=2200)
    unit: str | None = Field(default=None, max_length=128)
    boundary: str | None = Field(default=None, max_length=128)
    conversion_parameters: tuple[ConversionParameter, ...] = ()
    include_ineligible: bool = False
    limit: int = Field(default=20, ge=1, le=100)


class SearchCandidate(BaseModel):
    factor: dict[str, Any]
    score: float
    lexical_score: int
    concept_codes: tuple[str, ...]
    eligibility: EligibilityDecision
    geographic_coverage: GeographicEvaluation | None = None
    unit_conversion_status: ConversionStatus | None = None
    reason_codes: tuple[str, ...] = ()


class SearchResponse(BaseModel):
    query: str
    context: str
    calculation_profile: str
    policy_version: str
    items: tuple[SearchCandidate, ...]


class SemanticSearchEngine:
    def __init__(
        self,
        semantics: SemanticRegistry | None = None,
        units: UnitEngine | None = None,
        geography: GeographicCoverageEngine | None = None,
    ) -> None:
        self.semantics = semantics or SemanticRegistry()
        self.units = units or UnitEngine()
        self.geography = geography or GeographicCoverageEngine()

    def search(
        self,
        request: SearchRequest,
        factors: list[dict[str, Any]],
        *,
        query_concepts: tuple[str, ...] | None = None,
    ) -> SearchResponse:
        profile = (
            self.semantics.profile(request.calculation_profile)
            if request.calculation_profile
            else self.semantics.default_profile(request.context)
        )
        if profile.context != request.context:
            raise ValueError("calculation profile does not belong to requested context")
        if query_concepts is None:
            query_concepts = self.semantics.match_concepts(
                request.query, language=request.language
            )
        candidates = [
            self._candidate(request, profile.code, query_concepts, factor) for factor in factors
        ]
        if request.geography:
            candidates = [
                item
                for item in candidates
                if item.geographic_coverage is not None and item.geographic_coverage.eligible
            ]
        candidates = [item for item in candidates if not self._hard_rejected(item)]
        if not request.include_ineligible:
            candidates = [item for item in candidates if item.eligibility.calculation_eligible]
        candidates.sort(
            key=lambda item: (
                not item.eligibility.calculation_eligible,
                item.geographic_coverage.fallback_rank
                if item.geographic_coverage is not None
                else 0,
                -item.score,
                str(item.factor.get("factor_id", "")),
            )
        )
        selected = list(candidates[: request.limit])
        if (
            request.limit > 1
            and any(self._is_ipcc_derived_ghg(item.factor) for item in selected)
            and not any(item.factor.get("source_code") == "IPCC" for item in selected)
        ):
            primary = next(
                (
                    item
                    for item in candidates[request.limit :]
                    if item.factor.get("source_code") == "IPCC"
                    and item.eligibility.calculation_eligible
                ),
                None,
            )
            if primary is not None:
                selected[-1] = primary
        return SearchResponse(
            query=request.query,
            context=request.context,
            calculation_profile=profile.code,
            policy_version=self.semantics.version,
            items=tuple(selected),
        )

    def _candidate(
        self,
        request: SearchRequest,
        profile: str,
        query_concepts: tuple[str, ...],
        factor: dict[str, Any],
    ) -> SearchCandidate:
        eligibility = self.semantics.evaluate(profile, factor)
        geographic_coverage = (
            self.geography.evaluate(request.geography, factor) if request.geography else None
        )
        profile_rules = self.semantics.profile(profile)
        lexical = self._lexical_score(request.query, factor)
        factor_text = self.semantics.normalize(
            " ".join(
                str(factor.get(field, ""))
                for field in ("concept_code", "taxonomy_code", "activity_type", "name")
            )
        )
        matched_concepts = tuple(
            concept
            for concept in query_concepts
            if self.semantics.normalize(concept) in factor_text
        )
        if query_concepts and not matched_concepts:
            query_tail = {concept.rsplit(".", 1)[-1] for concept in query_concepts}
            matched_concepts = tuple(
                concept for concept in query_concepts if query_tail & set(factor_text.split())
            )
        concept_score = 100 if matched_concepts else 0
        if self._activity_concept_mismatch(query_concepts, factor):
            eligibility = EligibilityDecision(
                search_eligible=True,
                calculation_eligible=False,
                reason_codes=tuple((*eligibility.reason_codes, "activity_concept_mismatch")),
                profile=eligibility.profile,
                policy_version=eligibility.policy_version,
            )
        unit_status: ConversionStatus | None = None
        reasons = list(eligibility.reason_codes)
        unit_score = 100
        if request.unit:
            conversion = self.units.convert(
                ConversionRequest(
                    mode="activity",
                    value=Decimal("1"),
                    from_unit=request.unit,
                    to_unit=str(factor.get("activity_unit", "")),
                    parameters=request.conversion_parameters,
                )
            )
            unit_status = conversion.status
            if unit_status == ConversionStatus.EXACT_CONVERSION:
                unit_score = 100
            elif unit_status == ConversionStatus.CONDITIONAL_CONVERSION:
                unit_score = 60
                reasons.append("unit_conditional")
                conditional_ready = conversion.output_value is not None
                if not profile_rules.allow_conditional_conversion:
                    eligibility = EligibilityDecision(
                        search_eligible=True,
                        calculation_eligible=False,
                        reason_codes=tuple(
                            (
                                *eligibility.reason_codes,
                                "unit_conditional_denied",
                            )
                        ),
                        profile=eligibility.profile,
                        policy_version=eligibility.policy_version,
                    )
                elif not conditional_ready:
                    reasons.append("unit_parameter_required")
            else:
                unit_score = 0
                reasons.append("unit_incompatible")
                eligibility = EligibilityDecision(
                    search_eligible=True,
                    calculation_eligible=False,
                    reason_codes=tuple((*eligibility.reason_codes, "unit_incompatible")),
                    profile=eligibility.profile,
                    policy_version=eligibility.policy_version,
                )
            reasons = list(eligibility.reason_codes)
            if unit_status == ConversionStatus.CONDITIONAL_CONVERSION:
                reasons.append("unit_conditional")
                if (
                    profile_rules.allow_conditional_conversion
                    and conversion.output_value is None
                ):
                    reasons.append("unit_parameter_required")
            elif unit_status == ConversionStatus.INCOMPATIBLE:
                reasons.append("unit_incompatible")
        semantic_score = max(lexical, concept_score)
        context_score = 100 if eligibility.calculation_eligible else 0
        geography_score = (
            geographic_coverage.geographic_score if geographic_coverage is not None else 100
        )
        year_score = self._year_score(request.year, factor)
        score = round(
            semantic_score * 0.40
            + context_score * 0.20
            + geography_score * 0.20
            + year_score * 0.10
            + unit_score * 0.10,
            2,
        )
        return SearchCandidate(
            factor=factor,
            score=score,
            lexical_score=lexical,
            concept_codes=matched_concepts,
            eligibility=eligibility,
            geographic_coverage=geographic_coverage,
            unit_conversion_status=unit_status,
            reason_codes=tuple(dict.fromkeys(reasons)),
        )

    @staticmethod
    def _hard_rejected(candidate: SearchCandidate) -> bool:
        reasons = {*candidate.eligibility.reason_codes, *candidate.reason_codes}
        return bool(reasons & HARD_REJECTION_REASONS)

    @staticmethod
    def _lexical_score(query: str, factor: dict[str, Any]) -> int:
        needle = SemanticRegistry.normalize(query)
        haystack = SemanticRegistry.normalize(
            " ".join(
                str(factor.get(field, ""))
                for field in ("name", "description", "taxonomy_code", "activity_type")
            )
        )
        if needle == haystack:
            return 100
        if needle and needle in haystack:
            return 90
        tokens = set(needle.split())
        if not tokens:
            return 0
        overlap = len(tokens & set(haystack.split())) / len(tokens)
        return round(overlap * 80)

    @staticmethod
    def _year_score(requested: int | None, factor: dict[str, Any]) -> int:
        if requested is None:
            return 100
        factor_year = factor.get("reference_year")
        if factor_year is None:
            return 50
        if not isinstance(factor_year, int):
            return 50
        difference = abs(requested - factor_year)
        if difference <= 2:
            return 100
        data_quality = SemanticRegistry.normalize(str(factor.get("data_quality", "")))
        if difference <= 5 and "official annual" in data_quality:
            return 100
        if difference == 3:
            return 85
        return max(0, 70 - difference * 5)

    @staticmethod
    def _is_ipcc_derived_ghg(factor: dict[str, Any]) -> bool:
        if factor.get("source_code") != "GHG_PROTOCOL":
            return False
        details = (factor.get("methodology") or {}).get("details") or {}
        return "ipcc" in str(details.get("original_source", "")).casefold()

    @staticmethod
    def _activity_concept_mismatch(query_concepts: tuple[str, ...], factor: dict[str, Any]) -> bool:
        if "energy.natural_gas" not in query_concepts:
            return False
        taxonomy = SemanticRegistry.normalize(str(factor.get("taxonomy_code", "")))
        name = SemanticRegistry.normalize(str(factor.get("name", "")))
        activity_type = SemanticRegistry.normalize(str(factor.get("activity_type", "")))
        details = (factor.get("methodology") or {}).get("details") or {}
        application = SemanticRegistry.normalize(str(details.get("application", "")))
        return (
            ("electricity" in taxonomy and "natural gas" not in taxonomy)
            or "natural gas liquids" in name
            or "natural gasoline" in name
            or activity_type == "spend"
            or (
                activity_type == "transport energy"
                and ("from natural gas" in name or "from natural gas" in application)
                and not name.startswith("natural gas")
            )
        )
