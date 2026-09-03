from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResolvableTerm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_code: str
    family: str
    language: str
    term: str
    kind: str
    is_preferred: bool = False


class ConceptCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_code: str
    family: str
    language: str
    matched_term: str
    term_kind: str
    match_type: str
    score: int = Field(ge=0, le=100)


class MultilingualResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    detected_language: str | None = None
    script: str
    normalized_query: str
    folded_query: str
    tokens: tuple[str, ...]
    status: str
    candidates: tuple[ConceptCandidate, ...] = ()

    @property
    def concept_codes(self) -> tuple[str, ...]:
        return tuple(candidate.concept_code for candidate in self.candidates)


class MultilingualConceptResolver:
    """Deterministic runtime resolver over human-approved terminology."""

    def resolve(
        self,
        query: str,
        terms: list[ResolvableTerm],
        *,
        language: str | None = None,
        limit: int = 5,
    ) -> MultilingualResolution:
        normalized = self.normalize(query)
        folded = self.fold(normalized)
        tokens = tuple(normalized.split())
        detected = language or self.detect_language(query)
        if not normalized:
            return MultilingualResolution(
                query=query,
                detected_language=detected,
                script=self.script(query),
                normalized_query="",
                folded_query="",
                tokens=(),
                status="unresolved",
            )

        ranked: list[ConceptCandidate] = []
        for term in terms:
            score, match_type = self._score(normalized, folded, tokens, term)
            if score == 0:
                continue
            if detected and term.language == detected:
                score = min(100, score + 3)
            if language and term.language != language and score < 95:
                continue
            ranked.append(
                ConceptCandidate(
                    concept_code=term.concept_code,
                    family=term.family,
                    language=term.language,
                    matched_term=term.term,
                    term_kind=term.kind,
                    match_type=match_type,
                    score=score,
                )
            )

        ranked.sort(
            key=lambda item: (
                -item.score,
                item.term_kind not in {"canonical", "translation"},
                item.concept_code,
            )
        )
        unique: list[ConceptCandidate] = []
        seen: set[str] = set()
        for candidate in ranked:
            if candidate.concept_code in seen:
                continue
            seen.add(candidate.concept_code)
            unique.append(candidate)
            if len(unique) >= limit:
                break
        status = "unresolved"
        if unique:
            status = "resolved"
            if len(unique) > 1 and unique[0].score < 95 and unique[0].score - unique[1].score < 5:
                status = "ambiguous"
        return MultilingualResolution(
            query=query,
            detected_language=detected,
            script=self.script(query),
            normalized_query=normalized,
            folded_query=folded,
            tokens=tokens,
            status=status,
            candidates=tuple(unique),
        )

    def _score(
        self,
        normalized: str,
        folded: str,
        tokens: tuple[str, ...],
        term: ResolvableTerm,
    ) -> tuple[int, str]:
        target = self.normalize(term.term)
        target_folded = self.fold(target)
        target_tokens = tuple(target.split())
        preferred = term.is_preferred or term.kind in {"canonical", "translation"}
        if normalized == target:
            return (100 if preferred else 96), "exact_preferred" if preferred else "exact_alias"
        if folded and folded == target_folded:
            return (94 if preferred else 91), "accent_or_transliteration"
        if len(tokens) > 1 and set(tokens) == set(target_tokens):
            return 90, "all_tokens"
        if len(tokens) > 1 and set(tokens) <= set(target_tokens):
            return 84, "phrase_tokens"
        ratio = SequenceMatcher(None, folded, target_folded).ratio() if folded else 0
        if min(len(folded), len(target_folded)) >= 5 and ratio >= 0.82:
            return round(60 + (ratio - 0.82) * 100), "fuzzy"
        return 0, "none"

    @staticmethod
    def normalize(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).casefold().replace("_", " ")
        return " ".join(
            "".join(
                char
                if (char.isalnum() or unicodedata.category(char).startswith("M"))
                else " "
                for char in normalized
            ).split()
        )

    @staticmethod
    def fold(value: str) -> str:
        try:
            from unidecode import unidecode

            return " ".join(re.sub(r"[^a-z0-9]+", " ", unidecode(value).casefold()).split())
        except ImportError:  # pragma: no cover - minimal installation fallback
            return " ".join(
                re.sub(
                    r"[^a-z0-9]+",
                    " ",
                    "".join(
                        char
                        for char in unicodedata.normalize("NFKD", value.casefold())
                        if not unicodedata.combining(char)
                    ),
                ).split()
            )

    @staticmethod
    def script(value: str) -> str:
        names = [unicodedata.name(char, "") for char in value if char.isalpha()]
        for label in ("ARABIC", "CYRILLIC", "GREEK"):
            if any(label in name for name in names):
                return label.casefold()
        return "latin" if names else "unknown"

    @classmethod
    def detect_language(cls, value: str) -> str | None:
        script = cls.script(value)
        if script == "arabic":
            return "ar"
        if script == "cyrillic":
            return "ru"
        try:
            from lingua import Language

            detector = cls._language_detector()
            found = detector.detect_language_of(value)
            if found is None:
                return None
            language_codes: dict[Language, str] = {
                Language.ENGLISH: "en",
                Language.TURKISH: "tr",
                Language.GERMAN: "de",
                Language.FRENCH: "fr",
                Language.SPANISH: "es",
                Language.RUSSIAN: "ru",
                Language.ARABIC: "ar",
            }
            return language_codes.get(found)
        except ImportError:  # pragma: no cover - minimal installation fallback
            return None

    @staticmethod
    @lru_cache(maxsize=1)
    def _language_detector() -> Any:
        from lingua import Language, LanguageDetectorBuilder

        return LanguageDetectorBuilder.from_languages(
            Language.ENGLISH,
            Language.TURKISH,
            Language.GERMAN,
            Language.FRENCH,
            Language.SPANISH,
            Language.RUSSIAN,
            Language.ARABIC,
        ).build()
