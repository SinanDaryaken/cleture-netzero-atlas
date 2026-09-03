from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any, ClassVar

import pycountry
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from atlas.domain.enums import GeographicFitType, GeographyLevel


class GeographyNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    level: GeographyLevel
    name: str
    parent: str | None = None


class GeographicCoverageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    fit_scores: dict[GeographicFitType, int]
    fallback_order: tuple[GeographicFitType, ...]
    geographies: dict[str, GeographyNode]
    proxy_rules: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    country_aliases: dict[str, tuple[str, ...]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_complete_scores(self) -> GeographicCoverageConfig:
        missing = set(GeographicFitType) - set(self.fit_scores)
        if missing:
            raise ValueError(f"geographic fit scores are missing: {sorted(missing)}")
        invalid = {fit: score for fit, score in self.fit_scores.items() if not 0 <= score <= 100}
        if invalid:
            raise ValueError(f"geographic fit scores must be between 0 and 100: {invalid}")
        if set(self.fallback_order) != set(GeographicFitType):
            raise ValueError("fallback order must contain every geographic fit type once")
        return self


class GeographicEvaluation(BaseModel):
    requested_geography: str
    factor_geography: str
    geographic_fit: GeographicFitType
    geographic_score: int
    fallback_rank: int
    exact_geography: bool
    fallback_used: bool
    eligible: bool
    warning: str | None = None


class GeographyQueryResolution(BaseModel):
    original_query: str
    search_query: str
    geography_code: str
    geography_name: str
    matched_alias: str


class GeographicCoverageEngine:
    _ambiguous_alpha2: ClassVar[set[str]] = {
        "AS",
        "AT",
        "BE",
        "BY",
        "DO",
        "IN",
        "IS",
        "IT",
        "ME",
        "NO",
        "SO",
        "TO",
        "US",
    }

    def __init__(self, config_path: Path | None = None) -> None:
        path = config_path or Path(__file__).with_name("defaults.yaml")
        with path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"geographic coverage config must be a mapping: {path}")
        raw_geographies = payload.get("geographies", {})
        for country in pycountry.countries:
            raw_geographies.setdefault(
                str(country.alpha_2),
                {
                    "level": "country",
                    "name": str(country.name),
                    "parent": "GLOBAL",
                },
            )
        payload["geographies"] = {
            code: {"code": code, **definition} for code, definition in raw_geographies.items()
        }
        self.config = GeographicCoverageConfig.model_validate(payload)
        self._fallback_rank = {
            fit: index + 1 for index, fit in enumerate(self.config.fallback_order)
        }
        aliases: dict[tuple[str, ...], set[str]] = {}
        for code, node in self.config.geographies.items():
            if node.level != GeographyLevel.COUNTRY:
                continue
            country = pycountry.countries.get(alpha_2=code)
            values = {code, node.name}
            if country is not None:
                values.update(
                    str(value)
                    for value in (
                        getattr(country, "alpha_3", None),
                        getattr(country, "name", None),
                        getattr(country, "official_name", None),
                        getattr(country, "common_name", None),
                    )
                    if value
                )
            values.update(self.config.country_aliases.get(code, ()))
            for value in values:
                key = tuple(self._normalize_alias(value).split())
                if key:
                    aliases.setdefault(key, set()).add(code)
        self._country_aliases = aliases

    def list_geographies(self) -> tuple[GeographyNode, ...]:
        return tuple(
            sorted(
                self.config.geographies.values(),
                key=lambda item: (self.specificity(item.level), item.code),
            )
        )

    def geography(self, code: str) -> GeographyNode:
        normalized = self.resolve_code(code)
        try:
            return self.config.geographies[normalized]
        except KeyError as error:
            raise LookupError(f"unknown geography: {normalized}") from error

    def ancestors(self, code: str) -> tuple[str, ...]:
        node = self.geography(code)
        result: list[str] = []
        seen = {node.code}
        parent = node.parent
        while parent is not None:
            if parent in seen:
                raise ValueError(f"geography hierarchy contains a cycle at {parent}")
            seen.add(parent)
            result.append(parent)
            parent = self.geography(parent).parent
        return tuple(result)

    def search_codes(self, requested_code: str) -> tuple[str, ...]:
        normalized = self.resolve_code(requested_code)
        codes = [normalized, *self.ancestors(normalized)]
        codes.extend(self.config.proxy_rules.get(normalized, ()))
        return tuple(dict.fromkeys(codes))

    def resolve_code(self, value: str) -> str:
        direct = value.strip().upper()
        if direct in self.config.geographies:
            return direct
        key = tuple(self._normalize_alias(value).split())
        matches = self._country_aliases.get(key, set())
        if len(matches) == 1:
            return next(iter(matches))
        if len(matches) > 1:
            raise LookupError(f"ambiguous geography: {value}")
        raise LookupError(f"unknown geography: {value}")

    def extract_query_geography(self, query: str) -> GeographyQueryResolution | None:
        """Extract one unambiguous country qualifier without guessing its role."""

        normalized_tokens = self._normalize_alias(query).split()
        raw_tokens = query.split()
        candidates: list[tuple[int, int, str, str]] = []
        for alias, codes in self._country_aliases.items():
            if len(codes) != 1 or len(alias) > len(normalized_tokens):
                continue
            code = next(iter(codes))
            width = len(alias)
            for start in range(len(normalized_tokens) - width + 1):
                if tuple(normalized_tokens[start : start + width]) != alias:
                    continue
                if (
                    width == 1
                    and len(alias[0]) == 2
                    and code in self._ambiguous_alpha2
                    and (start >= len(raw_tokens) or raw_tokens[start] != code)
                ):
                    continue
                candidates.append((start, width, code, " ".join(alias)))
        if not candidates:
            return None
        resolved_codes = {candidate[2] for candidate in candidates}
        if len(resolved_codes) != 1:
            return None
        start, width, code, matched_alias = sorted(
            candidates, key=lambda item: (-item[1], item[0])
        )[0]
        remaining = normalized_tokens[:start] + normalized_tokens[start + width :]
        node = self.geography(code)
        return GeographyQueryResolution(
            original_query=query,
            search_query=" ".join(remaining),
            geography_code=code,
            geography_name=node.name,
            matched_alias=matched_alias,
        )

    def evaluate(self, requested_code: str, factor: dict[str, Any]) -> GeographicEvaluation:
        requested = self.geography(requested_code)
        fit = GeographicFitType(factor["geographic_fit_type"])
        geographies = factor.get("applicable_geographies") or []
        codes = [str(item["code"]).upper() for item in geographies]
        eligible_codes = self.search_codes(requested.code)
        matching_code = next((code for code in eligible_codes if code in codes), None)
        eligible = matching_code is not None

        factor_level = GeographyLevel(factor["geography_level"])
        exact = requested.code in codes and factor_level == requested.level
        rank = 0 if exact else self._fallback_rank[fit]
        fallback_used = eligible and not exact
        warning = None
        if fallback_used:
            warning = (
                f"No exact {requested.code} geography was selected; "
                f"using {matching_code} with {fit.value} fit"
            )
        return GeographicEvaluation(
            requested_geography=requested.code,
            factor_geography=matching_code or (codes[0] if codes else "UNKNOWN"),
            geographic_fit=fit,
            geographic_score=self.config.fit_scores[fit],
            fallback_rank=rank,
            exact_geography=exact,
            fallback_used=fallback_used,
            eligible=eligible,
            warning=warning,
        )

    @staticmethod
    def specificity(level: GeographyLevel) -> int:
        return {
            GeographyLevel.GLOBAL: 0,
            GeographyLevel.CONTINENT: 1,
            GeographyLevel.REGION: 2,
            GeographyLevel.COUNTRY: 3,
            GeographyLevel.STATE: 4,
            GeographyLevel.PROVINCE: 4,
            GeographyLevel.CITY: 5,
            GeographyLevel.GRID: 6,
            GeographyLevel.CUSTOM: 2,
        }[level]

    @staticmethod
    def _normalize_alias(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value.casefold())
        ascii_like = "".join(char for char in decomposed if not unicodedata.combining(char))
        return " ".join("".join(char if char.isalnum() else " " for char in ascii_like).split())
