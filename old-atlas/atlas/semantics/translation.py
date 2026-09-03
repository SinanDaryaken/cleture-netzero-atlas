from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from atlas.semantics.registry import ConceptLabel


class TranslationDraft(BaseModel):
    """Strict provider output. Every value remains a draft until a human approves it."""

    model_config = ConfigDict(extra="forbid")

    preferred_term: str = Field(min_length=1, max_length=255)
    definition: str = Field(min_length=1, max_length=2000)
    synonyms: list[str] = Field(default_factory=list, max_length=12)
    abbreviations: list[str] = Field(default_factory=list, max_length=8)
    protected_terms: list[str] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=20)


class TranslationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_code: str
    family: str
    canonical_name_en: str
    definition_en: str | None = None
    taxonomy_path: str | None = None
    sample_factor_names: tuple[str, ...] = ()
    activity_types: tuple[str, ...] = ()


class TranslationGroupItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_code: str
    translation: TranslationDraft


class TranslationGroupOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[TranslationGroupItem] = Field(min_length=1, max_length=50)


@dataclass(frozen=True)
class BatchSubmission:
    provider_job_id: str
    input_file_id: str
    custom_ids: dict[str, str]


@dataclass(frozen=True)
class GroupGeneration:
    provider_job_id: str
    custom_ids: dict[str, str]
    results: dict[str, TranslationDraft]


class DraftTranslator:
    """Creates review-required labels; persistence remains an explicit repository action."""

    def __init__(self, translate: Callable[[str, str, str], str], *, model: str) -> None:
        self._translate = translate
        self._model = model

    def draft(self, text: str, source_language: str, target_language: str) -> ConceptLabel:
        return ConceptLabel(
            language=target_language,
            label=self._translate(text, source_language, target_language),
            kind="translation",
            method="argos",
            model=self._model,
            confidence=None,
            review_status="draft",
        )


class OpenAITranslationProvider:
    """Contextual terminology generation over Responses API and Batch API."""

    prompt_version = "atlas-terminology-v1"

    def __init__(
        self,
        *,
        api_key: str,
        translation_model: str,
        qa_model: str,
        organization: str | None = None,
        project: str | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OpenAI API key is not configured")
        self._api_key = api_key
        self._organization = organization
        self._project = project
        self.translation_model = translation_model
        self.qa_model = qa_model

    def _client(self, *, timeout: float = 60.0) -> Any:
        try:
            from openai import OpenAI
        except ImportError as error:  # pragma: no cover - deployment dependency guard
            raise RuntimeError("install the translation dependency group to use OpenAI") from error
        return OpenAI(
            api_key=self._api_key,
            organization=self._organization,
            project=self._project,
            max_retries=3,
            timeout=timeout,
        )

    @staticmethod
    def _instructions(target_language: str, glossary: tuple[str, ...]) -> str:
        glossary_text = ", ".join(glossary) if glossary else "No additional glossary entries."
        return (
            "You are the terminology editor for an environmental emission-factor registry. "
            "Use the English concept as the semantic source of truth, not as a word-for-word "
            "template. Produce terminology that an ERP or sustainability user would naturally "
            f"search in language '{target_language}'. Preserve formulas, standards, source names, "
            "units, chemical symbols, GHG scopes and taxonomy identifiers. Do not invent a broader "
            "or narrower activity. Preferred terms must be concise noun phrases. Synonyms must be "
            "real search alternatives, not spelling noise. If the target language is English, edit "
            "the source into a clear canonical English term and definition. "
            f"Protected glossary: {glossary_text}"
        )

    @staticmethod
    def _input_text(item: TranslationInput, target_language: str) -> str:
        return json.dumps(
            {
                "target_language": target_language,
                "concept_code": item.concept_code,
                "family": item.family,
                "canonical_name_en": item.canonical_name_en,
                "definition_en": item.definition_en,
                "taxonomy_path": item.taxonomy_path,
                "sample_factor_names": list(item.sample_factor_names),
                "activity_types": list(item.activity_types),
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    def generate(
        self,
        item: TranslationInput,
        *,
        target_language: str,
        glossary: tuple[str, ...] = (),
        qa: bool = False,
    ) -> TranslationDraft:
        response = self._client(timeout=600.0).responses.parse(
            model=self.qa_model if qa else self.translation_model,
            input=[
                {"role": "system", "content": self._instructions(target_language, glossary)},
                {"role": "user", "content": self._input_text(item, target_language)},
            ],
            text_format=TranslationDraft,
        )
        if response.output_parsed is None:
            raise RuntimeError("OpenAI returned no structured translation output")
        return TranslationDraft.model_validate(response.output_parsed)

    def generate_group(
        self,
        items: Iterable[TranslationInput],
        *,
        target_language: str,
        glossary: tuple[str, ...] = (),
    ) -> GroupGeneration:
        source_items = tuple(items)
        if not source_items or len(source_items) > 50:
            raise ValueError("a direct response group must contain between 1 and 50 concepts")
        payload = {
            "target_language": target_language,
            "concepts": [
                json.loads(self._input_text(item, target_language)) for item in source_items
            ],
        }
        response = self._client(timeout=600.0).responses.parse(
            model=self.translation_model,
            input=[
                {
                    "role": "system",
                    "content": self._instructions(target_language, glossary)
                    + " Return exactly one item for every input concept. Copy each concept_code "
                    "verbatim and do not merge or omit concepts.",
                },
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False, sort_keys=True),
                },
            ],
            text_format=TranslationGroupOutput,
        )
        if response.output_parsed is None:
            raise RuntimeError("OpenAI returned no structured group output")
        parsed = TranslationGroupOutput.model_validate(response.output_parsed)
        expected = {item.concept_code for item in source_items}
        generated = {item.concept_code: item.translation for item in parsed.items}
        if set(generated) != expected or len(parsed.items) != len(expected):
            missing = sorted(expected - set(generated))
            extra = sorted(set(generated) - expected)
            raise ValueError(
                f"OpenAI group output does not match inputs; missing={missing}, extra={extra}"
            )
        custom_ids = {
            f"concept-{index:06d}": item.concept_code
            for index, item in enumerate(source_items, start=1)
        }
        results = {
            custom_id: generated[concept_code] for custom_id, concept_code in custom_ids.items()
        }
        return GroupGeneration(
            provider_job_id=str(response.id),
            custom_ids=custom_ids,
            results=results,
        )

    def group_results(
        self, provider_job_id: str, custom_ids: dict[str, str]
    ) -> dict[str, TranslationDraft]:
        """Recover a completed Responses group after interrupted Atlas persistence."""

        response = self._client(timeout=600.0).responses.retrieve(provider_job_id)
        parsed = TranslationGroupOutput.model_validate_json(response.output_text)
        generated = {item.concept_code: item.translation for item in parsed.items}
        expected = set(custom_ids.values())
        if set(generated) != expected or len(parsed.items) != len(expected):
            raise ValueError("stored OpenAI group output does not match the Atlas job")
        return {
            custom_id: generated[concept_code] for custom_id, concept_code in custom_ids.items()
        }

    def submit_batch(
        self,
        items: Iterable[TranslationInput],
        *,
        target_language: str,
        glossary: tuple[str, ...] = (),
    ) -> BatchSubmission:
        custom_ids: dict[str, str] = {}
        schema = TranslationDraft.model_json_schema()
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", suffix=".jsonl") as handle:
            for index, item in enumerate(items, start=1):
                custom_id = f"concept-{index:06d}"
                custom_ids[custom_id] = item.concept_code
                request = {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": "/v1/responses",
                    "body": {
                        "model": self.translation_model,
                        "input": [
                            {
                                "role": "system",
                                "content": self._instructions(target_language, glossary),
                            },
                            {
                                "role": "user",
                                "content": self._input_text(item, target_language),
                            },
                        ],
                        "text": {
                            "format": {
                                "type": "json_schema",
                                "name": "atlas_concept_translation",
                                "strict": True,
                                "schema": schema,
                            }
                        },
                    },
                }
                handle.write(json.dumps(request, ensure_ascii=False) + "\n")
            handle.flush()
            client = self._client()
            with open(handle.name, "rb") as batch_file:
                uploaded = client.files.create(file=batch_file, purpose="batch")
        batch = client.batches.create(
            input_file_id=uploaded.id,
            endpoint="/v1/responses",
            completion_window="24h",
            metadata={
                "atlas_prompt_version": self.prompt_version,
                "target_language": target_language,
            },
        )
        return BatchSubmission(
            provider_job_id=str(batch.id),
            input_file_id=str(uploaded.id),
            custom_ids=custom_ids,
        )

    def batch_status(self, provider_job_id: str) -> dict[str, Any]:
        batch = self._client().batches.retrieve(provider_job_id)
        return {
            "status": str(batch.status),
            "output_file_id": getattr(batch, "output_file_id", None),
            "error_file_id": getattr(batch, "error_file_id", None),
            "request_counts": (
                batch.request_counts.model_dump()
                if getattr(batch, "request_counts", None) is not None
                else {}
            ),
        }

    def cancel_batch(self, provider_job_id: str) -> str:
        """Cancel a submitted provider job when Atlas cannot persist its local record."""

        batch = self._client().batches.cancel(provider_job_id)
        return str(batch.status)

    def batch_results(self, output_file_id: str) -> dict[str, TranslationDraft]:
        content = self._client().files.content(output_file_id).text
        results: dict[str, TranslationDraft] = {}
        for line in content.splitlines():
            if not line.strip():
                continue
            envelope = json.loads(line)
            custom_id = str(envelope["custom_id"])
            body = (envelope.get("response") or {}).get("body") or {}
            output_text = self._response_output_text(body)
            results[custom_id] = TranslationDraft.model_validate_json(output_text)
        return results

    @staticmethod
    def _response_output_text(body: dict[str, Any]) -> str:
        for output in body.get("output") or []:
            for content in output.get("content") or []:
                if content.get("type") == "output_text" and content.get("text"):
                    return str(content["text"])
        raise ValueError("batch response has no output_text")


def argos_translate(text: str, source_language: str, target_language: str) -> str:
    os.environ.setdefault("ARGOS_CHUNK_TYPE", "MINISBD")
    try:
        from argostranslate import translate  # type: ignore[import-untyped]
    except ImportError as error:
        raise RuntimeError("install the translation dependency group to use Argos") from error
    translation = translate.get_translation_from_codes(source_language, target_language)
    if translation is None:
        raise LookupError(
            f"Argos language pair is not installed: {source_language}->{target_language}"
        )
    return str(translation.translate(text))
