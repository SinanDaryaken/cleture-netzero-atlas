from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import yaml


def normalize_text(value: str) -> str:
    folded = (
        value.casefold()
        .replace("\u0131", "i")
        .replace("\u00f8", "o")
        .replace("\u00df", "ss")
    )
    ascii_text = "".join(
        char for char in unicodedata.normalize("NFKD", folded) if not unicodedata.combining(char)
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_text).split())


class RecommendationPolicy:
    """Versioned, source-neutral serving policy for recommendation projections."""

    def __init__(self, path: Path | None = None) -> None:
        policy_path = path or Path(__file__).with_name("policy.yaml")
        payload = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("recommendation policy must be a mapping")
        self.version = str(payload["version"])
        self.families: dict[str, dict[str, Any]] = dict(payload["families"])
        self._family_terms: dict[str, tuple[tuple[str, frozenset[str]], ...]] = {
            code: tuple(
                (normalized, frozenset(normalized.split()))
                for term in definition["terms"]
                if (normalized := normalize_text(str(term)))
            )
            for code, definition in self.families.items()
        }
        self._factor_terms: dict[str, tuple[tuple[str, frozenset[str]], ...]] = {
            code: tuple(
                (normalized, frozenset(normalized.split()))
                for term in definition.get("factor_terms", definition["terms"])
                if (normalized := normalize_text(str(term)))
            )
            for code, definition in self.families.items()
        }
        self.source_authority: dict[str, int] = {
            str(code): int(rank) for code, rank in payload["default_source_authority"].items()
        }
        self.official_sources = frozenset(str(code) for code in payload["official_sources"])
        self.jurisdictions: dict[str, dict[str, Any]] = dict(payload.get("jurisdictions", {}))
        self.fallback_tiers: tuple[dict[str, Any], ...] = tuple(payload["fallback_tiers"])
        categories = tuple(dict(item) for item in payload.get("scope3_categories", ()))
        self._scope3_categories = {int(item["code"]): item for item in categories}
        if set(self._scope3_categories) != set(range(1, 16)):
            raise ValueError("recommendation policy must define Scope 3 categories 1 through 15")

    def resolve_family(
        self,
        text: str,
        *,
        allow_partial: bool = True,
    ) -> tuple[str, dict[str, Any]]:
        needle = normalize_text(text)
        if not needle:
            return "unknown", {
                "concept_code": None,
                "calculation_role": "unknown",
                "activity_basis": "unknown",
                "default_scope": None,
            }
        needle_terms = frozenset(needle.split())
        matches: list[tuple[int, str, dict[str, Any]]] = []
        for code, definition in self.families.items():
            score = max(
                (
                    100 if term == needle else
                    85 if term in needle else
                    70 if term_words <= needle_terms else
                    60 if allow_partial and (needle in term or term_words & needle_terms) else 0
                )
                for term, term_words in self._family_terms[code]
            )
            if score:
                matches.append((score, code, definition))
        if not matches:
            return "unknown", {
                "concept_code": None,
                "calculation_role": "unknown",
                "activity_basis": "unknown",
                "default_scope": None,
            }
        matches.sort(key=lambda item: (-item[0], item[1]))
        return matches[0][1], matches[0][2]

    def family_for_concept(self, concept_code: str | None) -> tuple[str, dict[str, Any]] | None:
        if not concept_code:
            return None
        for code, definition in self.families.items():
            if str(definition.get("concept_code") or "") == concept_code:
                return code, definition
        return None

    def resolve_factor_family(self, text: str) -> tuple[str, dict[str, Any]]:
        """Resolve curated factors with whole-term matching, never loose token overlap."""

        needle = normalize_text(text)
        needle_terms = frozenset(needle.split())
        matches: list[tuple[int, str, dict[str, Any]]] = []
        for code, definition in self.families.items():
            score = max(
                (
                    100 if term == needle else
                    85 if term in needle else
                    70 if term_words <= needle_terms else 0
                )
                for term, term_words in self._factor_terms[code]
            )
            if score:
                matches.append((score, code, definition))
        if not matches:
            return "unknown", {}
        matches.sort(key=lambda item: (-item[0], item[1]))
        return matches[0][1], matches[0][2]

    def classify_factor(self, factor: dict[str, Any]) -> dict[str, Any] | None:
        existing = factor.get("applicability")
        if (
            isinstance(existing, dict)
            and existing.get("family_code")
            and existing.get("policy_version") == self.version
        ):
            return dict(existing)

        searchable = " ".join(
            str(value or "")
            for value in (
                factor.get("concept_code"),
                factor.get("taxonomy_code"),
                factor.get("activity_type"),
                factor.get("name"),
            )
        )
        taxonomy_hint = normalize_text(str(factor.get("taxonomy_code") or ""))
        activity_hint = normalize_text(str(factor.get("activity_type") or ""))
        if activity_hint == "spend":
            raw_taxonomy = str(factor.get("taxonomy_code") or "").casefold()
            service_prefixes = self.families["purchased_services"].get(
                "classification_prefixes", ()
            )
            if not any(
                raw_taxonomy.startswith(str(prefix).casefold()) for prefix in service_prefixes
            ):
                return None
            family_code, definition = "purchased_services", self.families["purchased_services"]
        elif "energy electricity" in taxonomy_hint or "electricity generation" in activity_hint:
            family_code, definition = "electricity", self.families["electricity"]
        else:
            family_code, definition = self.resolve_factor_family(searchable)
        if family_code == "unknown":
            return None

        methodology = factor.get("methodology") or {}
        declared_scope = normalize_text(str(methodology.get("scope") or "")).replace(" ", "_")
        normalized_scope = next(
            (scope for scope in ("scope_1", "scope_2", "scope_3") if scope in declared_scope),
            "",
        )
        scope: str | None = normalized_scope or str(definition.get("default_scope") or "") or None
        role = str(definition["calculation_role"])
        qualifiers: dict[str, str] = {}
        name = normalize_text(str(factor.get("name") or ""))
        taxonomy = normalize_text(str(factor.get("taxonomy_code") or ""))
        activity_type = normalize_text(str(factor.get("activity_type") or ""))

        if family_code == "natural_gas" and (
            "natural gas liquids" in name
            or "from natural gas" in name
            or activity_type == "transport energy"
        ):
            return None
        if family_code == "diesel" and (
            "biodiesel" in name or activity_type == "transport energy"
        ):
            return None
        if family_code == "gasoline" and (
            "aviation gasoline" in name
            or "aviation spirit" in name
            or "jet gasoline" in name
            or "biogasoline" in name
            or "bio gasoline" in name
            or "bio petrol" in name
            or "ethanol gasoline" in name
            or "e85" in name
            or activity_type == "transport energy"
        ):
            return None

        if family_code == "electricity":
            if "fuel generation" in taxonomy or "electricity generation" in activity_type:
                role = "electricity_generation"
            else:
                role = "purchased_electricity"
            if "distribution" in name or "dagitim" in name:
                qualifiers["connection_level"] = "distribution"
            elif "transmission" in name or "iletim" in name:
                qualifiers["connection_level"] = "transmission"
            elif "gross generation" in name or "uretimi" in name:
                qualifiers["connection_level"] = "generation"
        elif family_code == "refrigerants":
            gas = next(
                (
                    token.upper()
                    for token in ("r134a", "r410a", "r32", "r404a", "r407c")
                    if token in name
                ),
                None,
            )
            if gas:
                qualifiers["gas"] = gas
        elif family_code == "air_travel":
            for haul in ("domestic", "short haul", "long haul", "international"):
                if haul in name:
                    qualifiers["haul"] = haul.replace(" ", "_")
                    break
            if "radiative forcing" in name or "with rf" in name:
                qualifiers["radiative_forcing"] = "included"
        elif family_code == "waste":
            details = methodology.get("details") or {}
            material = details.get("material")
            if material:
                qualifiers["material"] = str(material)
            for treatment in ("landfill", "recycling", "compost", "incineration"):
                if treatment in name:
                    qualifiers["treatment"] = treatment
                    break

        boundary = normalize_text(str(methodology.get("system_boundary") or "")).replace(" ", "_")
        if boundary == "national_inventory_implied_factor":
            role = "national_inventory_implied"
        fallback_class = self._fallback_class(factor)
        scope3_categories = (
            tuple(int(code) for code in definition.get("scope3_categories", ()))
            if scope == "scope_3"
            else ()
        )
        return {
            "concept_code": definition.get("concept_code"),
            "family_code": family_code,
            "calculation_role": role,
            "calculation_method": "activity_factor",
            "scope_category": scope,
            "scope3_categories": scope3_categories,
            "activity_basis": definition["activity_basis"],
            "boundary": boundary or None,
            "fallback_class": fallback_class,
            "qualifiers": qualifiers,
            "policy_version": self.version,
            "review_status": "projected",
        }

    def scope3_category(self, code: int) -> dict[str, Any]:
        try:
            category = self._scope3_categories[code]
        except KeyError as error:
            raise LookupError(f"unknown Scope 3 category: {code}") from error
        return {
            **category,
            "supported_families": [
                family_code
                for family_code, definition in self.families.items()
                if code in definition.get("scope3_categories", ())
            ],
        }

    def scope3_category_catalog(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.scope3_category(code) for code in sorted(self._scope3_categories))

    def scope3_categories_for_family(self, family_code: str) -> tuple[int, ...]:
        definition = self.families.get(family_code, {})
        return tuple(int(code) for code in definition.get("scope3_categories", ()))

    def scope3_required_qualifiers(self, family_code: str) -> tuple[str, ...]:
        definition = self.families.get(family_code, {})
        return tuple(str(item) for item in definition.get("scope3_required_qualifiers", ()))

    def authority_rank(self, factor: dict[str, Any], country: str) -> int:
        source = str(factor.get("source_code") or "")
        overrides = self.jurisdictions.get(country.upper(), {}).get("source_authority", {})
        if source in overrides:
            return int(overrides[source])
        return self.source_authority.get(source, 50)

    def classification_hints(
        self,
        family_code: str,
        query: str,
        explicit: dict[str, str],
    ) -> tuple[str, ...]:
        hints = []
        for value in explicit.values():
            if not value:
                continue
            code = str(value)
            if family_code == "purchased_services" and code.isdigit():
                code = f"atlas.spend.economic_sector.{code}"
            hints.append(code)
        definition = self.families.get(family_code, {})
        normalized = normalize_text(query)
        for term, prefixes in definition.get("query_classifications", {}).items():
            if normalize_text(str(term)) in normalized:
                hints.extend(str(prefix) for prefix in prefixes)
        return tuple(dict.fromkeys(hints))

    def _fallback_class(self, factor: dict[str, Any]) -> str:
        fit = str(factor.get("geographic_fit_type") or "")
        source = str(factor.get("source_code") or "")
        level = str(factor.get("geography_level") or "")
        if level == "country" and fit == "country_specific" and source in self.official_sources:
            return "country_official"
        if level == "country":
            return "country_modelled"
        if fit == "regional" or level in {"region", "continent"}:
            return "regional"
        if fit == "global" or level == "global":
            return "global"
        return "foreign_proxy"

    @staticmethod
    def profile_scope(profile: str) -> str | None:
        normalized = normalize_text(profile).replace(" ", "_")
        for scope in ("scope1", "scope2", "scope3"):
            if scope in normalized:
                return scope.replace("scope", "scope_")
        return None
