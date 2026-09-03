from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

HARD_REJECTION_REASONS = frozenset(
    {
        "entity_type_denied",
        "factor_kind_denied",
        "intended_use_denied",
        "scope_unknown",
        "scope_denied",
        "not_published",
        "quality_denied",
        "activity_concept_mismatch",
        "unit_incompatible",
        "unit_conditional_denied",
    }
)


class ConceptLabel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    language: str = Field(pattern=r"^[a-z]{2}$")
    label: str = Field(min_length=1, max_length=255)
    kind: str = Field(pattern=r"^(canonical|translation|synonym|abbreviation|deprecated)$")
    method: str = "curated"
    model: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    review_status: str = Field(
        default="approved", pattern=r"^(draft|approved|rejected|superseded)$"
    )


class CanonicalConcept(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(pattern=r"^[a-z0-9_.-]+$")
    family: str
    canonical_name_en: str
    labels: tuple[ConceptLabel, ...]


class CalculationProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(pattern=r"^[a-z0-9_.-]+$")
    context: str = Field(pattern=r"^[a-z0-9_]+$")
    allowed_entity_types: tuple[str, ...]
    allowed_factor_value_kinds: tuple[str, ...]
    allowed_intended_uses: tuple[str, ...]
    allowed_scopes: tuple[str, ...] = ()
    allow_conditional_conversion: bool = False


class EligibilityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    search_eligible: bool
    calculation_eligible: bool
    reason_codes: tuple[str, ...] = ()
    profile: str
    policy_version: str


class ConceptResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str
    normalized_query: str
    detected_language: str | None = None
    concept_code: str | None = None
    confidence: float = Field(ge=0, le=1)
    search_terms: tuple[str, ...] = ()


class SemanticRegistry:
    def __init__(self, config_path: Path | None = None) -> None:
        path = config_path or Path(__file__).with_name("registry.yaml")
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.version = str(payload["version"])
        self._concepts = {
            concept.code: concept
            for item in payload.get("concepts", [])
            if (concept := CanonicalConcept.model_validate(item))
        }
        self._profiles = {
            profile.code: profile
            for item in payload.get("profiles", [])
            if (profile := CalculationProfile.model_validate(item))
        }
        self._context_defaults = {
            str(context): str(profile)
            for context, profile in payload.get("context_defaults", {}).items()
        }
        self._target_languages = tuple(str(item) for item in payload.get("target_languages", []))

    def concepts(self) -> tuple[CanonicalConcept, ...]:
        return tuple(sorted(self._concepts.values(), key=lambda item: item.code))

    def profiles(self) -> tuple[CalculationProfile, ...]:
        return tuple(sorted(self._profiles.values(), key=lambda item: item.code))

    def contexts(self) -> tuple[str, ...]:
        return tuple(sorted(self._context_defaults))

    def target_languages(self) -> tuple[str, ...]:
        return self._target_languages

    def profile(self, code: str) -> CalculationProfile:
        try:
            return self._profiles[code]
        except KeyError as error:
            raise LookupError(f"unknown calculation profile: {code}") from error

    def default_profile(self, context: str) -> CalculationProfile:
        try:
            return self.profile(self._context_defaults[context])
        except KeyError as error:
            raise LookupError(f"unknown calculation context: {context}") from error

    def evaluate(self, profile_code: str, factor: dict[str, Any]) -> EligibilityDecision:
        profile = self.profile(profile_code)
        reasons: list[str] = []
        entity_type = str(factor.get("entity_type", "emission_factor"))
        factor_kind = str(factor.get("factor_value_kind", ""))
        intended_use = str(factor.get("intended_use", ""))
        if entity_type not in profile.allowed_entity_types:
            reasons.append("entity_type_denied")
        if factor_kind not in profile.allowed_factor_value_kinds:
            reasons.append("factor_kind_denied")
        if intended_use not in profile.allowed_intended_uses:
            reasons.append("intended_use_denied")
        if profile.allowed_scopes:
            actual_scope = self._effective_scope(factor)
            allowed_scopes = {self.normalize(scope) for scope in profile.allowed_scopes}
            if not actual_scope:
                reasons.append("scope_unknown")
            elif actual_scope not in allowed_scopes:
                reasons.append("scope_denied")
        if factor.get("published") is False:
            reasons.append("not_published")
        if factor.get("quality_eligible") is False:
            reasons.append("quality_denied")
        return EligibilityDecision(
            search_eligible=True,
            calculation_eligible=not reasons,
            reason_codes=tuple(reasons),
            profile=profile.code,
            policy_version=self.version,
        )

    def _effective_scope(self, factor: dict[str, Any]) -> str:
        methodology = factor.get("methodology") or {}
        declared_scope = methodology.get("scope")
        if declared_scope is not None and str(declared_scope).strip():
            return self.normalize(str(declared_scope))

        if (
            factor.get("activity_type") == "energy"
            and factor.get("entity_type", "emission_factor")
            in {"emission_factor", "implied_emission_factor"}
            and factor.get("factor_value_kind") == "co2e_total"
            and factor.get("intended_use") == "inventory"
            and self.normalize(str(methodology.get("system_boundary", "")))
            == "national inventory implied factor"
        ):
            return self.normalize("scope_1")

        return ""

    def match_concepts(self, query: str, *, language: str | None = None) -> tuple[str, ...]:
        needle = self.normalize(query)
        matches: list[tuple[int, str]] = []
        for concept in self._concepts.values():
            best = 0
            for label in concept.labels:
                if language and label.language != language:
                    continue
                normalized = self.normalize(label.label)
                if needle == normalized:
                    best = max(best, 100)
                elif needle in normalized or normalized in needle:
                    best = max(best, 85)
                elif set(needle.split()) & set(normalized.split()):
                    best = max(best, 60)
            if best:
                matches.append((best, concept.code))
        matches.sort(key=lambda item: (-item[0], item[1]))
        return tuple(code for _, code in matches)

    def resolve_concept(self, query: str) -> ConceptResolution:
        needle = self.normalize(query)
        detected_language: str | None = None
        best: tuple[int, CanonicalConcept] | None = None
        for concept in self._concepts.values():
            for label in concept.labels:
                if label.review_status != "approved":
                    continue
                normalized = self.normalize(label.label)
                score = 0
                if needle == normalized:
                    score = 100
                elif needle in normalized or normalized in needle:
                    score = 85
                elif set(needle.split()) & set(normalized.split()):
                    score = 60
                if score and (best is None or score > best[0]):
                    best = (score, concept)
                    detected_language = label.language
        if best is None:
            return ConceptResolution(
                query=query,
                normalized_query=needle,
                confidence=0,
                search_terms=(needle,),
            )
        score, concept = best
        terms = tuple(
            dict.fromkeys(
                self.normalize(label.label)
                for label in concept.labels
                if label.review_status == "approved"
            )
        )
        return ConceptResolution(
            query=query,
            normalized_query=needle,
            detected_language=detected_language,
            concept_code=concept.code,
            confidence=score / 100,
            search_terms=terms,
        )

    @staticmethod
    def normalize(value: str) -> str:
        return " ".join(re.sub(r"[\W_]+", " ", value.casefold()).split())
