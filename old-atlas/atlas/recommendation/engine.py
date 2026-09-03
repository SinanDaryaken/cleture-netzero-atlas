from __future__ import annotations

from decimal import Decimal
from typing import Any

from atlas.geography import GeographicCoverageEngine
from atlas.recommendation.models import (
    CalculationPlan,
    RecommendationCandidate,
    RecommendationIntent,
    RecommendationRank,
    RecommendationRequest,
    RecommendationResponse,
)
from atlas.recommendation.policy import RecommendationPolicy, normalize_text
from atlas.units import ConversionRequest, ConversionStatus, UnitEngine


class RecommendationEngine:
    """Turns a published factor pool into explainable, calculation-ready choices."""

    def __init__(
        self,
        geography: GeographicCoverageEngine | None = None,
        units: UnitEngine | None = None,
        policy: RecommendationPolicy | None = None,
    ) -> None:
        self.geography = geography or GeographicCoverageEngine()
        self.units = units or UnitEngine()
        self.policy = policy or RecommendationPolicy()

    def recommend(
        self,
        request: RecommendationRequest,
        factors: list[dict[str, Any]],
        *,
        resolved_concept_code: str | None = None,
    ) -> RecommendationResponse:
        intent = self._intent(request, resolved_concept_code=resolved_concept_code)
        assumptions: list[str] = []
        assumed_qualifiers: set[str] = set()
        questions: list[dict[str, Any]] = []

        if intent.scope_category == "scope_3":
            compatible_categories = self.policy.scope3_categories_for_family(
                intent.family_code
            )
            requested_category = request.activity.scope3_category
            if requested_category is None and not compatible_categories:
                return self._response(
                    status="no_applicable_factor",
                    intent=intent,
                    trace=(
                        self._trace("intent", "pass", intent.model_dump()),
                        self._trace(
                            "scope3_category",
                            "fail",
                            {
                                "reason": "family_not_supported",
                                "family_code": intent.family_code,
                            },
                        ),
                    ),
                )
            if requested_category is None and (
                request.mode == "strict" or len(compatible_categories) != 1
            ):
                options = [
                    self.policy.scope3_category(code)
                    for code in compatible_categories
                ]
                questions.append(
                    {
                        "field": "activity.scope3_category",
                        "message": "Select the GHG Protocol Scope 3 category for this activity.",
                        "options": options,
                    }
                )
                return self._response(
                    status="needs_input",
                    intent=intent,
                    questions=questions,
                    trace=(
                        self._trace("intent", "pass", intent.model_dump()),
                        self._trace(
                            "scope3_category",
                            "warning",
                            {"compatible_categories": list(compatible_categories)},
                        ),
                    ),
                )
            if requested_category is None:
                requested_category = compatible_categories[0]
                intent.scope3_category = requested_category
                category = self.policy.scope3_category(requested_category)
                assumptions.append(
                    f"Scope 3 category {requested_category} ({category['name']}) "
                    "was inferred from the activity family."
                )
            elif requested_category not in compatible_categories:
                category = self.policy.scope3_category(requested_category)
                return self._response(
                    status="no_applicable_factor",
                    intent=intent,
                    trace=(
                        self._trace("intent", "pass", intent.model_dump()),
                        self._trace(
                            "scope3_category",
                            "fail",
                            {
                                "reason": "family_category_mismatch",
                                "category": category,
                                "family_code": intent.family_code,
                                "compatible_categories": list(compatible_categories),
                            },
                        ),
                    ),
                )
            required_qualifiers = self.policy.scope3_required_qualifiers(
                intent.family_code
            )
            missing_qualifiers = [
                qualifier
                for qualifier in required_qualifiers
                if not intent.qualifiers.get(qualifier)
            ]
            if missing_qualifiers:
                qualifier_options = {
                    "haul": ["domestic", "short_haul", "long_haul", "international"],
                    "treatment": ["landfill", "recycling", "compost", "incineration"],
                }
                questions.extend(
                    {
                        "field": f"activity.qualifiers.{qualifier}",
                        "message": (
                            f"Scope 3 category {intent.scope3_category} requires "
                            f"an explicit {qualifier.replace('_', ' ')}."
                        ),
                        "options": qualifier_options.get(qualifier, []),
                    }
                    for qualifier in missing_qualifiers
                )
                return self._response(
                    status="needs_input",
                    intent=intent,
                    assumptions=assumptions,
                    questions=questions,
                    trace=(
                        self._trace("intent", "pass", intent.model_dump()),
                        self._trace(
                            "scope3_inputs",
                            "warning",
                            {"missing_qualifiers": missing_qualifiers},
                        ),
                    ),
                )

        if (
            intent.family_code == "electricity"
            and request.context == "corporate_carbon"
            and intent.scope_category == "scope_2"
            and "connection_level" not in intent.qualifiers
        ):
            if request.mode == "strict":
                questions.append(
                    {
                        "field": "facility_context.electricity_connection_level",
                        "message": (
                            "Is the facility connected at distribution or transmission level?"
                        ),
                        "options": ["distribution", "transmission"],
                    }
                )
                return self._response(
                    status="needs_input",
                    intent=intent,
                    assumptions=assumptions,
                    questions=questions,
                    trace=(self._trace("intent", "pass", intent.model_dump()),),
                )
            intent.qualifiers["connection_level"] = "distribution"
            assumed_qualifiers.add("connection_level")
            assumptions.append(
                "Electricity connection level was not supplied; distribution was assumed."
            )

        ranked: list[RecommendationCandidate] = []
        rejected: dict[str, int] = {}
        for factor in factors:
            result, reason = self._candidate(
                request,
                intent,
                factor,
                tuple(assumptions),
                frozenset(assumed_qualifiers),
            )
            if result is None:
                rejected[reason] = rejected.get(reason, 0) + 1
            else:
                ranked.append(result)

        ranked.sort(key=self._sort_key)
        if not ranked:
            return self._response(
                status="no_applicable_factor",
                intent=intent,
                assumptions=assumptions,
                questions=questions,
                trace=(
                    self._trace("intent", "pass", intent.model_dump()),
                    self._trace("candidate_gates", "fail", {"rejected": rejected}),
                ),
            )

        selected = ranked[0]
        alternatives = self._alternatives_with_lineage(selected, ranked[1:], request.limit - 1)
        calculation = self._calculation(request, selected)
        proxy = selected.rank.tier == "foreign_proxy"
        if selected.conversion.required_parameters:
            status = "conversion_parameter_required"
        elif proxy:
            status = "proxy_recommended"
        else:
            status = "recommended"
        return self._response(
            status=status,
            intent=intent,
            recommended=selected,
            alternatives=tuple(alternatives),
            assumptions=assumptions,
            questions=questions,
            calculation=calculation,
            trace=(
                self._trace("intent", "pass", intent.model_dump()),
                self._trace(
                    "candidate_gates", "pass", {"eligible": len(ranked), "rejected": rejected}
                ),
                self._trace(
                    "selection",
                    "warning" if proxy or selected.conversion.required_parameters else "pass",
                    {
                        "factor_id": selected.factor.get("factor_id"),
                        "tier": selected.rank.tier,
                        "grade": selected.rank.grade,
                    },
                ),
            ),
        )

    def _intent(
        self,
        request: RecommendationRequest,
        *,
        resolved_concept_code: str | None = None,
    ) -> RecommendationIntent:
        resolved_family = self.policy.family_for_concept(resolved_concept_code)
        if resolved_family is None:
            family_code, definition = self.policy.resolve_family(request.activity.text)
        else:
            family_code, definition = resolved_family
        qualifiers = {str(key): str(value) for key, value in request.activity.qualifiers.items()}
        if request.facility_context.electricity_connection_level:
            qualifiers.setdefault(
                "connection_level", request.facility_context.electricity_connection_level
            )
        text = normalize_text(request.activity.text)
        if family_code == "air_travel":
            for haul in ("domestic", "short haul", "long haul", "international"):
                if haul in text:
                    qualifiers.setdefault("haul", haul.replace(" ", "_"))
                    break
        elif family_code == "refrigerants":
            for gas in ("r134a", "r410a", "r32", "r404a", "r407c"):
                if gas in text:
                    qualifiers.setdefault("gas", gas.upper())
                    break
        elif family_code == "waste":
            for treatment in ("landfill", "recycling", "compost", "incineration"):
                if treatment in text:
                    qualifiers.setdefault("treatment", treatment)
                    break
        scope = self.policy.profile_scope(request.calculation_profile)
        return RecommendationIntent(
            family_code=family_code,
            concept_code=definition.get("concept_code"),
            calculation_role=str(definition["calculation_role"]),
            scope_category=scope or definition.get("default_scope"),
            scope3_category=request.activity.scope3_category,
            activity_basis=str(definition["activity_basis"]),
            qualifiers=qualifiers,
        )

    def _candidate(
        self,
        request: RecommendationRequest,
        intent: RecommendationIntent,
        factor: dict[str, Any],
        assumptions: tuple[str, ...],
        assumed_qualifiers: frozenset[str],
    ) -> tuple[RecommendationCandidate | None, str]:
        applicability = self.policy.classify_factor(factor)
        if applicability is None or applicability["family_code"] != intent.family_code:
            return None, "concept_mismatch"
        if not self._context_allowed(request.context, factor):
            return None, "context_denied"
        if applicability["calculation_role"] != intent.calculation_role:
            return None, "calculation_role_mismatch"
        if intent.scope_category and applicability.get("scope_category") != intent.scope_category:
            return None, "scope_mismatch"
        if intent.scope3_category is not None and intent.scope3_category not in tuple(
            int(code) for code in applicability.get("scope3_categories", ())
        ):
            return None, "scope3_category_mismatch"
        qualifier_rank = self._qualifier_rank(
            intent.qualifiers,
            applicability.get("qualifiers") or {},
            assumed_qualifiers,
        )
        if qualifier_rank is None:
            return None, "qualifier_mismatch"

        conversion = self.units.convert(
            ConversionRequest(
                mode="activity",
                value=request.activity.quantity,
                from_unit=request.activity.unit,
                to_unit=str(factor.get("activity_unit") or ""),
                parameters=request.conversion_parameters,
            )
        )
        if conversion.status == ConversionStatus.INCOMPATIBLE:
            return None, "unit_incompatible"

        geography = self.geography.evaluate(request.facility_context.country, factor)
        is_foreign_proxy = not geography.eligible
        if is_foreign_proxy and not request.accept_proxy:
            return None, "proxy_acceptance_required"
        tier, geography_rank = self._geography_tier(
            geography.model_dump(), applicability, is_foreign_proxy
        )
        geography_payload = geography.model_dump(mode="json")
        if is_foreign_proxy:
            geography_payload.update(
                {
                    "eligible": True,
                    "fallback_used": True,
                    "warning": "Foreign geography is offered only because accept_proxy=true.",
                }
            )

        unit_rank = (
            0
            if request.activity.unit == str(factor.get("activity_unit"))
            else 2
            if conversion.required_parameters
            else 1
        )
        year = factor.get("reference_year")
        temporal = abs(request.year - int(year)) if request.year and year is not None else 999
        authority = self.policy.authority_rank(factor, request.facility_context.country)
        grade = "A" if geography_rank <= 1 and qualifier_rank == 0 else "B"
        if tier in {"global", "regional"}:
            grade = "B"
        if tier == "foreign_proxy":
            grade = "D"
        elif conversion.required_parameters and grade == "A":
            grade = "B"
        rank = RecommendationRank(
            applicability=0,
            qualifier=qualifier_rank,
            geography=geography_rank,
            authority=authority,
            temporal=temporal,
            unit=unit_rank,
            grade=grade,
            tier=tier,
        )
        reasons = ["concept_exact", "role_exact", "scope_exact"]
        if intent.scope3_category is not None:
            reasons.append("scope3_category_exact")
        if qualifier_rank:
            reasons.append("qualifier_unspecified")
        reasons.append(f"geography_{tier}")
        reasons.append(
            "unit_parameter_required" if conversion.required_parameters else "unit_convertible"
        )
        return (
            RecommendationCandidate(
                factor=factor,
                applicability=applicability,
                rank=rank,
                geography=geography_payload,
                conversion=conversion,
                lineage=self._lineage(factor),
                assumptions=assumptions,
                reason_codes=tuple(reasons),
            ),
            "eligible",
        )

    @staticmethod
    def _context_allowed(context: str, factor: dict[str, Any]) -> bool:
        entity = str(factor.get("entity_type") or "emission_factor")
        kind = str(factor.get("factor_value_kind") or "")
        intended = str(factor.get("intended_use") or "")
        if context in {"corporate_carbon", "freight"}:
            return (
                entity in {"emission_factor", "implied_emission_factor"}
                and kind == "co2e_total"
                and intended == "inventory"
            )
        if context == "cbam":
            return entity == "embodied_emission_factor" and intended == "calculation_input"
        if context in {"lca", "pcf"}:
            return entity in {"lca_result", "characterization_result", "epd"}
        return False

    @staticmethod
    def _qualifier_rank(
        expected: dict[str, str],
        actual: dict[str, str],
        assumed: frozenset[str],
    ) -> int | None:
        rank = 0
        for key, value in expected.items():
            if key == "connection_level" and actual.get(key) == "generation":
                return None
            if key in actual and normalize_text(actual[key]) != normalize_text(value):
                return None
            if key in {"gas", "haul", "treatment", "connection_level"} and key not in actual:
                if key not in assumed:
                    return None
                rank = max(rank, 1)
        return rank

    @staticmethod
    def _geography_tier(
        geography: dict[str, Any], applicability: dict[str, Any], proxy: bool
    ) -> tuple[str, int]:
        if proxy:
            return "foreign_proxy", 4
        if geography.get("exact_geography"):
            fallback = str(applicability.get("fallback_class") or "")
            if fallback == "country_official":
                return "country_official", 0
            return "country_modelled", 1
        fit = str(geography.get("geographic_fit") or "")
        if fit == "regional":
            return "regional", 2
        return "global", 3

    @staticmethod
    def _sort_key(item: RecommendationCandidate) -> tuple[Any, ...]:
        rank = item.rank
        return (
            rank.applicability,
            rank.qualifier,
            rank.geography,
            rank.authority,
            rank.temporal,
            rank.unit,
            str(item.factor.get("factor_id") or ""),
        )

    @staticmethod
    def _lineage(factor: dict[str, Any]) -> dict[str, Any]:
        details = (factor.get("methodology") or {}).get("details") or {}
        original = str(details.get("original_source") or "")
        derived_from = []
        if "ipcc" in original.casefold():
            derived_from.append(
                {
                    "source_code": "IPCC",
                    "description": original,
                    "relationship": "derived_from",
                }
            )
        return {
            "source_code": factor.get("source_code"),
            "source_factor_id": factor.get("source_factor_id"),
            "derived_from": derived_from,
        }

    @staticmethod
    def _alternatives_with_lineage(
        selected: RecommendationCandidate,
        candidates: list[RecommendationCandidate],
        limit: int,
    ) -> list[RecommendationCandidate]:
        alternatives = list(candidates[: max(0, limit)])
        selected_factor = selected.factor
        details = (selected_factor.get("methodology") or {}).get("details") or {}
        if (
            str(selected_factor.get("source_code")) == "GHG_PROTOCOL"
            and "ipcc" in str(details.get("original_source") or "").casefold()
            and not any(item.factor.get("source_code") == "IPCC" for item in alternatives)
        ):
            ipcc = next(
                (item for item in candidates if item.factor.get("source_code") == "IPCC"),
                None,
            )
            if ipcc is not None and limit > 0:
                if len(alternatives) < limit:
                    alternatives.append(ipcc)
                else:
                    alternatives[-1] = ipcc
        return alternatives

    def _calculation(
        self, request: RecommendationRequest, selected: RecommendationCandidate
    ) -> CalculationPlan:
        factor = selected.factor
        conversion = selected.conversion
        result_value = None
        result_unit = None
        if conversion.output_value is not None:
            result_value = conversion.output_value * Decimal(str(factor["factor_value"]))
            try:
                result_unit = self.units.parse(str(factor["factor_unit"])).numerator.code
            except LookupError:
                result_unit = str(factor["factor_unit"]).split("/", 1)[0]
        normalized = conversion.output_value
        return CalculationPlan(
            original_value=request.activity.quantity,
            original_unit=request.activity.unit,
            normalized_value=normalized,
            normalized_unit=str(factor["activity_unit"]),
            factor_value=Decimal(str(factor["factor_value"])),
            factor_unit=str(factor["factor_unit"]),
            result_value=result_value,
            result_unit=result_unit,
            formula=(
                f"{normalized} {factor['activity_unit']} * "
                f"{factor['factor_value']} {factor['factor_unit']}"
                if normalized is not None
                else "calculation blocked until the required conversion parameter is supplied"
            ),
        )

    @staticmethod
    def _trace(stage: str, status: str, details: dict[str, Any]) -> dict[str, Any]:
        return {"stage": stage, "status": status, "details": details}

    def _response(self, **values: Any) -> RecommendationResponse:
        return RecommendationResponse(
            policy_version=self.policy.version,
            versions={
                "recommendation_policy": self.policy.version,
                "unit_registry": self.units.version,
                "geography_policy": self.geography.config.version,
            },
            **values,
        )
