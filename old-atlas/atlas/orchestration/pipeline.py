from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from atlas.domain.enums import PIPELINE_STEPS, PipelineStep, RunOutcome, StepStatus
from atlas.domain.models import PipelineContext, PipelineRun, SourceDefinition
from atlas.ingestion.errors import RetryableIngestionError
from atlas.ports.adapters import AtlasSourceAdapter
from atlas.ports.repositories import NullRunRepository, RunRepository


class PipelineEngine:
    """Executes the fixed v1 pipeline without knowing source implementation details."""

    def __init__(self, run_repository: RunRepository | None = None) -> None:
        self._runs = run_repository or NullRunRepository()

    async def execute(
        self,
        source: SourceDefinition,
        adapter: AtlasSourceAdapter,
        *,
        run: PipelineRun | None = None,
        attempt: int = 1,
    ) -> PipelineContext:
        current_run = run or PipelineRun(source_code=source.code)
        context = PipelineContext(source=source, run=current_run)
        await self._runs.save(current_run)

        for step in PIPELINE_STEPS:
            if current_run.outcome != RunOutcome.RUNNING:
                await self._skip(current_run, step)
                continue

            state = current_run.steps[step]
            state.status = StepStatus.RUNNING
            state.started_at = datetime.now(UTC)
            state.attempt = attempt
            await self._runs.save(current_run)

            try:
                result = await self._invoke(step, adapter, context)
                self._apply_result(step, context, result)
            except Exception as error:  # worker must persist every unexpected failure
                state.status = StepStatus.FAILED
                state.finished_at = datetime.now(UTC)
                state.message = str(error)
                current_run.outcome = RunOutcome.FAILED
                current_run.failure_retryable = isinstance(error, RetryableIngestionError)
                current_run.error_class = type(error).__name__
                current_run.finished_at = state.finished_at
                await self._runs.save(current_run)
                continue

            state.finished_at = datetime.now(UTC)
            if step == PipelineStep.CHECK and context.check_result is not None:
                state.status = StepStatus.SUCCESS
                current_run.requested_revision = context.check_result.revision
                if not context.check_result.changed:
                    state.message = context.check_result.reason
                    current_run.outcome = RunOutcome.NO_CHANGE
                    current_run.finished_at = state.finished_at
            elif step == PipelineStep.VALIDATE and context.quality_report is not None:
                if context.quality_report.requires_review:
                    state.status = StepStatus.REVIEW_REQUIRED
                    context.review_required = True
                elif context.quality_report.has_warnings:
                    state.status = StepStatus.WARNING
                else:
                    state.status = StepStatus.SUCCESS
            elif step == PipelineStep.COMPARE and context.comparison_report is not None:
                if context.comparison_report.requires_review:
                    state.status = StepStatus.REVIEW_REQUIRED
                    state.message = "; ".join(context.comparison_report.review_reasons)
                    context.review_required = True
                else:
                    state.status = StepStatus.SUCCESS
            else:
                state.status = StepStatus.SUCCESS

            if step == PipelineStep.VERSION and context.review_required:
                current_run.outcome = RunOutcome.REVIEW_REQUIRED
                current_run.finished_at = state.finished_at
            elif step == PipelineStep.PUBLISH:
                current_run.outcome = RunOutcome.SUCCESS
                current_run.finished_at = state.finished_at
            await self._runs.save(current_run)

        return context

    async def _skip(self, run: PipelineRun, step: PipelineStep) -> None:
        state = run.steps[step]
        if state.status == StepStatus.PENDING:
            state.status = StepStatus.SKIPPED
            state.finished_at = datetime.now(UTC)
            await self._runs.save(run)

    @staticmethod
    async def _invoke(
        step: PipelineStep,
        adapter: AtlasSourceAdapter,
        context: PipelineContext,
    ) -> Any:
        handler = getattr(adapter, step.value)
        return await handler(context)

    @staticmethod
    def _apply_result(step: PipelineStep, context: PipelineContext, result: Any) -> None:
        target_by_step = {
            PipelineStep.CHECK: "check_result",
            PipelineStep.FETCH: "fetched_asset",
            PipelineStep.STORE_RAW: "raw_asset",
            PipelineStep.PARSE: "parsed_records",
            PipelineStep.NORMALIZE: "normalized_factors",
            PipelineStep.VALIDATE: "quality_report",
            PipelineStep.COMPARE: "comparison_report",
            PipelineStep.VERSION: "dataset_version_id",
        }
        target = target_by_step.get(step)
        if target is not None:
            setattr(context, target, result)
