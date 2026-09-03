import asyncio
import json
import sys
from typing import Any

from atlas.config import get_settings
from atlas.infrastructure.database import Database
from atlas.infrastructure.database.repositories import AtlasRepository
from atlas.semantics import (
    DraftTranslator,
    OpenAITranslationProvider,
    SemanticRegistry,
    argos_translate,
)
from atlas.units import UnitEngine


async def rebuild() -> dict[str, int]:
    database = Database(get_settings())
    try:
        repository = AtlasRepository(database.sessions)
        return await repository.rebuild_intelligence_index(UnitEngine(), SemanticRegistry())
    finally:
        await database.dispose()


async def coverage() -> dict[str, object]:
    database = Database(get_settings())
    try:
        repository = AtlasRepository(database.sessions)
        semantics = SemanticRegistry()
        return await repository.intelligence_coverage(target_languages=semantics.target_languages())
    finally:
        await database.dispose()


async def translate() -> dict[str, Any]:
    settings = get_settings()
    database = Database(settings)
    try:
        repository = AtlasRepository(database.sessions)
        semantics = SemanticRegistry()
        if settings.translation_provider == "argos":
            translator = DraftTranslator(argos_translate, model="argos-offline")
            return await repository.generate_missing_concept_translations(
                translator,
                target_languages=semantics.target_languages(),
            )
        if settings.openai_api_key is None:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI translation")
        target = settings.translation_target_language
        inputs = await repository.translation_inputs(
            target_language=target,
            only_missing=True,
        )
        if not inputs:
            return {"target_language": target, "status": "nothing_to_translate"}
        glossary = await repository.glossary_terms(target_language=target)
        glossary_version = await repository.glossary_version(target_language=target)
        provider = OpenAITranslationProvider(
            api_key=settings.openai_api_key.get_secret_value(),
            translation_model=settings.openai_translation_model,
            qa_model=settings.openai_qa_model,
            organization=settings.openai_organization,
            project=settings.openai_project,
        )
        jobs: list[dict[str, Any]] = []
        failure: dict[str, Any] | None = None
        chunks = [
            inputs[offset : offset + settings.translation_batch_size]
            for offset in range(0, len(inputs), settings.translation_batch_size)
        ]
        for batch_index, chunk in enumerate(chunks, start=1):
            try:
                submission = await asyncio.to_thread(
                    provider.submit_batch,
                    chunk,
                    target_language=target,
                    glossary=glossary,
                )
            except Exception as error:
                failure = {
                    "batch_index": batch_index,
                    "stage": "provider_submission",
                    "message": str(error)[:1000],
                }
                break
            try:
                jobs.append(
                    await repository.create_translation_job(
                        provider_job_id=submission.provider_job_id,
                        input_file_id=submission.input_file_id,
                        target_language=target,
                        model=provider.translation_model,
                        qa_model=provider.qa_model,
                        prompt_version=provider.prompt_version,
                        glossary_version=glossary_version,
                        custom_ids=submission.custom_ids,
                        requested_by=settings.translation_requested_by,
                    )
                )
            except Exception as error:
                cleanup_status = "cancel_failed"
                try:
                    cleanup_status = await asyncio.to_thread(
                        provider.cancel_batch, submission.provider_job_id
                    )
                except Exception:
                    pass
                failure = {
                    "batch_index": batch_index,
                    "stage": "local_persistence",
                    "provider_job_id": submission.provider_job_id,
                    "cleanup_status": cleanup_status,
                    "message": str(error)[:1000],
                }
                break
        if not jobs and failure:
            raise RuntimeError(f"OpenAI batch submission failed: {failure['message']}")
        submitted = sum(int(job["requested_count"]) for job in jobs)
        return {
            "status": "partial" if failure else "submitted",
            "target_language": target,
            "batch_size": settings.translation_batch_size,
            "batch_count": len(jobs),
            "requested_count": submitted,
            "remaining_count": len(inputs) - submitted,
            "jobs": jobs,
            "failure": failure,
        }
    finally:
        await database.dispose()


def run() -> None:
    print(json.dumps(asyncio.run(rebuild()), sort_keys=True))


def run_check() -> None:
    result = asyncio.run(coverage())
    print(json.dumps(result, sort_keys=True))
    if not bool(result["ready"]):
        sys.exit(1)


def run_translate() -> None:
    print(json.dumps(asyncio.run(translate()), sort_keys=True))


if __name__ == "__main__":
    run()
