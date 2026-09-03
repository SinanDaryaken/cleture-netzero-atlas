from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import Text, and_, cast, delete, func, insert, or_, select, text, type_coerce
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from atlas.domain.enums import (
    PIPELINE_STEPS,
    DatasetVersionStatus,
    OutboxStatus,
    ReviewStatus,
    RunMode,
    RunOutcome,
    SourceHistoryStrategy,
    TemporalVersionStatus,
)
from atlas.domain.models import (
    ChangeCheckResult,
    PipelineContext,
    PipelineRun,
    RawAssetReference,
    SourceDefinition,
)
from atlas.infrastructure.database.models import (
    ConceptLabelRow,
    ConceptRow,
    ConversionParameterRow,
    CountryLabelRow,
    CountryRow,
    DatasetRow,
    DatasetVersionRow,
    FacilityRow,
    FactorApplicabilityRow,
    FactorConceptRow,
    FactorRow,
    FactorSectorAssignmentRow,
    FactorUnitExpressionRow,
    FactorVersionRow,
    FallbackPolicyRow,
    GlossaryEntryRow,
    LicenseRow,
    OutboxEventRow,
    ProcessingArtifactRow,
    ProvenanceRow,
    QualityResultRow,
    RawAssetRow,
    RegressionCaseRow,
    RegressionResultRow,
    RegressionReviewRow,
    RegressionRunRow,
    ReviewRow,
    RunStepRow,
    SectorCategoryRow,
    SectorLabelRow,
    SectorRow,
    SourceCheckRow,
    SourceObservationRow,
    SourceRow,
    SourceRunRow,
    TaxonomyRow,
    TranslationJobRow,
    UnitAliasRow,
    UnitDefinitionRow,
    UnitExpressionMappingRow,
    utc_now,
)
from atlas.ports.repositories import RunRepository
from atlas.sectors import SECTOR_CATEGORIES, SECTOR_REGISTRY, SectorPolicy

if TYPE_CHECKING:
    from atlas.recommendation import RecommendationPolicy
    from atlas.semantics import (
        ConceptLabel,
        DraftTranslator,
        SemanticRegistry,
        TranslationDraft,
        TranslationInput,
    )
    from atlas.units import UnitEngine


def _normalize_search_text(value: str) -> str:
    return " ".join(re.sub(r"[\W_]+", " ", value.casefold()).split())


def _normalize_country_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    ascii_like = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^\w]+", " ", ascii_like).split())


def _reference_year_preference(
    requested_year: int | None,
    candidate_year: int | None,
    rank: int = 0,
) -> tuple[int, int, int, int, int]:
    """Prefer a dated version closest to the request; use UNDATED only as a fallback."""

    if candidate_year is None:
        return (1, 0, 0, 0, rank)
    if requested_year is None:
        return (0, 0, 0, -candidate_year, rank)
    return (
        0,
        abs(requested_year - candidate_year),
        1 if candidate_year > requested_year else 0,
        -candidate_year,
        rank,
    )


def _canonical_concept_code(taxonomy_code: str | None, source_code: str) -> str:
    raw = (taxonomy_code or f"source.{source_code.casefold()}.uncategorized").casefold()
    if raw.startswith("atlas."):
        raw = raw[6:]
    normalized = re.sub(r"[^a-z0-9_.-]+", ".", raw).strip(".")
    return (normalized or f"source.{source_code.casefold()}.uncategorized")[:255]


def _canonical_concept_name(concept_code: str, *, source_code: str, sample_name: str | None) -> str:
    if source_code == "OPEN_CEDA" and sample_name:
        return sample_name.split(" — ", 1)[0][:255]
    words = concept_code.replace("_", " ").replace(".", " ").replace("-", " ").split()
    return " ".join(
        word.upper() if any(char.isdigit() for char in word) else word.title() for word in words
    )[:255]


@dataclass(frozen=True)
class RunRequest:
    run_id: UUID
    created: bool


@dataclass(frozen=True)
class OutboxMessage:
    id: UUID
    event_type: str
    payload: dict[str, Any]
    attempts: int


class AtlasRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions
        self._sector_policy = SectorPolicy()

    async def list_facilities(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        statement = select(FacilityRow).order_by(FacilityRow.code)
        if active_only:
            statement = statement.where(FacilityRow.active.is_(True))
        async with self._sessions() as session:
            rows = list((await session.execute(statement)).scalars())
        return [self._facility_payload(row) for row in rows]

    async def get_facility(self, code: str) -> dict[str, Any] | None:
        async with self._sessions() as session:
            row = await session.get(FacilityRow, code.upper())
        return self._facility_payload(row) if row is not None and row.active else None

    async def upsert_facility(
        self,
        *,
        code: str,
        name: str,
        country_code: str,
        region: str | None,
        electricity_connection_level: str | None,
        industry_codes: dict[str, str],
        metadata: dict[str, Any],
        registry_version: str,
        active: bool,
    ) -> dict[str, Any]:
        normalized_code = code.upper()
        normalized_country = country_code.upper()
        if electricity_connection_level not in {None, "distribution", "transmission"}:
            raise ValueError("invalid electricity connection level")
        async with self._sessions.begin() as session:
            if await session.get(CountryRow, normalized_country) is None:
                raise LookupError(f"unknown country: {normalized_country}")
            row = await session.get(FacilityRow, normalized_code, with_for_update=True)
            if row is None:
                row = FacilityRow(
                    code=normalized_code,
                    name=name,
                    country_code=normalized_country,
                    registry_version=registry_version,
                )
                session.add(row)
            row.name = name
            row.country_code = normalized_country
            row.region = region
            row.electricity_connection_level = electricity_connection_level
            row.industry_codes = industry_codes
            row.metadata_json = metadata
            row.registry_version = registry_version
            row.active = active
            await session.flush()
            payload = self._facility_payload(row)
        return payload

    async def create_conversion_parameter(
        self,
        *,
        name: str,
        value: Decimal,
        unit: str,
        source: str,
        country_code: str | None,
        facility_code: str | None,
        valid_from: date | None,
        valid_to: date | None,
        provenance: dict[str, Any],
        version: str,
    ) -> dict[str, Any]:
        if value <= 0:
            raise ValueError("conversion parameter value must be positive")
        if valid_from is not None and valid_to is not None and valid_to < valid_from:
            raise ValueError("valid_to must be on or after valid_from")
        normalized_country = country_code.upper() if country_code else None
        normalized_facility = facility_code.upper() if facility_code else None
        async with self._sessions.begin() as session:
            if normalized_country and await session.get(CountryRow, normalized_country) is None:
                raise LookupError(f"unknown country: {normalized_country}")
            if normalized_facility:
                facility = await session.get(FacilityRow, normalized_facility)
                if facility is None:
                    raise LookupError(f"unknown facility: {normalized_facility}")
                if normalized_country and facility.country_code != normalized_country:
                    raise ValueError("facility and parameter country do not match")
                normalized_country = normalized_country or facility.country_code
            row = ConversionParameterRow(
                name=name,
                value=value,
                unit=unit,
                source=source,
                country_code=normalized_country,
                facility_code=normalized_facility,
                valid_from=valid_from,
                valid_to=valid_to,
                provenance=provenance,
                review_status="draft",
                version=version,
            )
            session.add(row)
            await session.flush()
            payload = self._conversion_parameter_payload(row)
        return payload

    async def conversion_parameters(
        self,
        *,
        name: str | None = None,
        country_code: str | None = None,
        facility_code: str | None = None,
        effective_on: date | None = None,
        review_status: str = "approved",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        statement = select(ConversionParameterRow).where(
            ConversionParameterRow.active.is_(True),
            ConversionParameterRow.review_status == review_status,
        )
        if name:
            statement = statement.where(ConversionParameterRow.name == name)
        if facility_code:
            normalized_facility = facility_code.upper()
            statement = statement.where(
                or_(
                    ConversionParameterRow.facility_code == normalized_facility,
                    ConversionParameterRow.facility_code.is_(None),
                )
            )
        if country_code:
            normalized_country = country_code.upper()
            statement = statement.where(
                or_(
                    ConversionParameterRow.country_code == normalized_country,
                    ConversionParameterRow.country_code.is_(None),
                )
            )
        if effective_on:
            statement = statement.where(
                or_(
                    ConversionParameterRow.valid_from.is_(None),
                    ConversionParameterRow.valid_from <= effective_on,
                ),
                or_(
                    ConversionParameterRow.valid_to.is_(None),
                    ConversionParameterRow.valid_to >= effective_on,
                ),
            )
        statement = statement.order_by(
            ConversionParameterRow.facility_code.desc().nullslast(),
            ConversionParameterRow.country_code.desc().nullslast(),
            ConversionParameterRow.valid_from.desc().nullslast(),
            ConversionParameterRow.created_at.desc(),
        ).limit(limit)
        async with self._sessions() as session:
            rows = list((await session.execute(statement)).scalars())
        return [self._conversion_parameter_payload(row) for row in rows]

    async def decide_conversion_parameter(
        self,
        parameter_id: UUID,
        *,
        decision: str,
        reviewed_by: str,
        note: str | None,
    ) -> dict[str, Any]:
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")
        async with self._sessions.begin() as session:
            row = await session.get(ConversionParameterRow, parameter_id, with_for_update=True)
            if row is None:
                raise LookupError("conversion parameter not found")
            if row.review_status != "draft":
                raise ValueError("only draft conversion parameters can be reviewed")
            row.review_status = decision
            row.reviewed_by = reviewed_by
            row.reviewed_at = utc_now()
            row.review_note = note
            await session.flush()
            payload = self._conversion_parameter_payload(row)
        return payload

    async def record_regression_run(
        self,
        *,
        suite_version: str,
        requested_by: str,
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        counts = {
            key: sum(item["status"] == key for item in results)
            for key in ("passed", "changed", "failed")
        }
        run_status = (
            "passed" if counts["failed"] == 0 and counts["changed"] == 0 else "review_required"
        )
        async with self._sessions.begin() as session:
            run = RegressionRunRow(
                suite_version=suite_version,
                status=run_status,
                total=len(results),
                passed=counts["passed"],
                changed=counts["changed"],
                failed=counts["failed"],
                requested_by=requested_by,
                completed_at=utc_now(),
            )
            session.add(run)
            await session.flush()
            for item in results:
                case_code = str(item["id"])
                case = await session.get(RegressionCaseRow, case_code)
                if case is None:
                    case = RegressionCaseRow(
                        code=case_code,
                        name=case_code,
                        suite_version=suite_version,
                        expected={"display": str(item["expected"])},
                    )
                    session.add(case)
                session.add(
                    RegressionResultRow(
                        run_id=run.id,
                        case_code=case_code,
                        status=str(item["status"]),
                        actual=str(item["actual"]),
                        expected=str(item["expected"]),
                        details=dict(item.get("details") or {}),
                    )
                )
            await session.flush()
            payload = self._regression_run_payload(run, results=results)
        return payload

    async def regression_runs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        async with self._sessions() as session:
            runs = list(
                (
                    await session.execute(
                        select(RegressionRunRow)
                        .order_by(RegressionRunRow.created_at.desc())
                        .limit(limit)
                    )
                ).scalars()
            )
        return [self._regression_run_payload(run) for run in runs]

    async def get_regression_run(self, run_id: UUID) -> dict[str, Any] | None:
        async with self._sessions() as session:
            run = await session.get(RegressionRunRow, run_id)
            if run is None:
                return None
            results = list(
                (
                    await session.execute(
                        select(RegressionResultRow)
                        .where(RegressionResultRow.run_id == run_id)
                        .order_by(RegressionResultRow.case_code)
                    )
                ).scalars()
            )
            review = await session.scalar(
                select(RegressionReviewRow).where(RegressionReviewRow.run_id == run_id)
            )
        payload = self._regression_run_payload(
            run,
            results=[self._regression_result_payload(item) for item in results],
        )
        payload["review"] = self._regression_review_payload(review) if review else None
        return payload

    async def review_regression_run(
        self,
        run_id: UUID,
        *,
        decision: str,
        reviewed_by: str,
        note: str | None,
    ) -> dict[str, Any]:
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision must be approved or rejected")
        async with self._sessions.begin() as session:
            run = await session.get(RegressionRunRow, run_id, with_for_update=True)
            if run is None:
                raise LookupError("regression run not found")
            review = await session.scalar(
                select(RegressionReviewRow)
                .where(RegressionReviewRow.run_id == run_id)
                .with_for_update()
            )
            if review is None:
                review = RegressionReviewRow(
                    run_id=run_id, decision=decision, reviewed_by=reviewed_by
                )
                session.add(review)
            review.decision = decision
            review.reviewed_by = reviewed_by
            review.note = note
            review.reviewed_at = utc_now()
            run.status = decision
            await session.flush()
        payload = await self.get_regression_run(run_id)
        if payload is None:
            raise LookupError("regression run not found")
        return payload

    @staticmethod
    def _facility_payload(row: FacilityRow) -> dict[str, Any]:
        return {
            "code": row.code,
            "name": row.name,
            "country_code": row.country_code,
            "region": row.region,
            "electricity_connection_level": row.electricity_connection_level,
            "industry_codes": row.industry_codes,
            "metadata": row.metadata_json,
            "registry_version": row.registry_version,
            "active": row.active,
        }

    @staticmethod
    def _conversion_parameter_payload(row: ConversionParameterRow) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "name": row.name,
            "value": row.value,
            "unit": row.unit,
            "source": row.source,
            "country_code": row.country_code,
            "facility_code": row.facility_code,
            "valid_from": row.valid_from,
            "valid_to": row.valid_to,
            "provenance": row.provenance,
            "review_status": row.review_status,
            "reviewed_by": row.reviewed_by,
            "reviewed_at": row.reviewed_at,
            "review_note": row.review_note,
            "version": row.version,
            "active": row.active,
        }

    @staticmethod
    def _regression_result_payload(row: RegressionResultRow) -> dict[str, Any]:
        return {
            "id": row.case_code,
            "status": row.status,
            "actual": row.actual,
            "expected": row.expected,
            "details": row.details,
        }

    @staticmethod
    def _regression_review_payload(row: RegressionReviewRow) -> dict[str, Any]:
        return {
            "decision": row.decision,
            "reviewed_by": row.reviewed_by,
            "note": row.note,
            "reviewed_at": row.reviewed_at,
        }

    @staticmethod
    def _regression_run_payload(
        row: RegressionRunRow, *, results: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": str(row.id),
            "suite_version": row.suite_version,
            "status": row.status,
            "total": row.total,
            "passed": row.passed,
            "changed": row.changed,
            "failed": row.failed,
            "requested_by": row.requested_by,
            "created_at": row.created_at,
            "completed_at": row.completed_at,
        }
        if results is not None:
            payload["items"] = results
        return payload

    async def list_sectors(self, *, language: str = "en") -> list[dict[str, Any]]:
        requested_language = language.casefold()
        async with self._sessions() as session:
            sectors = list(
                (
                    await session.execute(
                        select(SectorRow)
                        .where(SectorRow.active.is_(True))
                        .order_by(SectorRow.canonical_name)
                    )
                ).scalars()
            )
            labels = list(
                (
                    await session.execute(
                        select(SectorLabelRow).where(
                            SectorLabelRow.sector_code.in_(sector.code for sector in sectors),
                            SectorLabelRow.language.in_((requested_language, "en")),
                            SectorLabelRow.review_status == "approved",
                        )
                    )
                ).scalars()
            )
            categories = list(
                (
                    await session.execute(
                        select(SectorCategoryRow)
                        .where(SectorCategoryRow.active.is_(True))
                        .order_by(SectorCategoryRow.name_en)
                    )
                ).scalars()
            )
            count_rows = (
                await session.execute(
                    select(
                        FactorSectorAssignmentRow.sector_code,
                        FactorSectorAssignmentRow.category_code,
                        func.count(FactorSectorAssignmentRow.factor_version_id),
                    )
                    .join(
                        FactorVersionRow,
                        FactorVersionRow.id == FactorSectorAssignmentRow.factor_version_id,
                    )
                    .join(
                        DatasetVersionRow,
                        DatasetVersionRow.id == FactorVersionRow.dataset_version_id,
                    )
                    .where(
                        DatasetVersionRow.status == DatasetVersionStatus.PUBLISHED.value,
                        FactorVersionRow.version_status == TemporalVersionStatus.CURRENT.value,
                    )
                    .group_by(
                        FactorSectorAssignmentRow.sector_code,
                        FactorSectorAssignmentRow.category_code,
                    )
                )
            ).all()

        preferred: dict[tuple[str, str], str] = {
            (label.sector_code, label.language): label.label for label in labels
        }
        counts = {
            (str(sector_code), str(category_code)): int(count)
            for sector_code, category_code, count in count_rows
        }
        category_payload: dict[str, list[dict[str, Any]]] = {}
        for category in categories:
            category_payload.setdefault(category.sector_code, []).append(
                {
                    "code": category.code,
                    "name": category.name_tr if requested_language == "tr" else category.name_en,
                    "count": counts.get((category.sector_code, category.code), 0),
                }
            )
        return [
            {
                "code": sector.code,
                "name": preferred.get((sector.code, requested_language))
                or preferred.get((sector.code, "en"))
                or sector.canonical_name,
                "canonical_name": sector.canonical_name,
                "description": sector.description,
                "registry_version": sector.registry_version,
                "count": sum(
                    counts.get((sector.code, category.code), 0)
                    for category in categories
                    if category.sector_code == sector.code
                ),
                "categories": category_payload.get(sector.code, []),
            }
            for sector in sectors
        ]

    async def _ensure_sector_registry(self, session: AsyncSession) -> None:
        existing_sector_codes = set(await session.scalars(select(SectorRow.code)))
        new_sectors = [
            SectorRow(
                code=definition.code,
                canonical_name=definition.name_en,
                description=definition.description,
                registry_version=self._sector_policy.version,
                active=True,
            )
            for definition in SECTOR_REGISTRY
            if definition.code not in existing_sector_codes
        ]
        session.add_all(new_sectors)
        if new_sectors:
            await session.flush()

        existing_category_codes = set(await session.scalars(select(SectorCategoryRow.code)))
        session.add_all(
            [
                SectorCategoryRow(
                    code=definition.code,
                    sector_code=definition.sector_code,
                    name_en=definition.name_en,
                    name_tr=definition.name_tr,
                    registry_version=self._sector_policy.version,
                    active=True,
                )
                for definition in SECTOR_CATEGORIES
                if definition.code not in existing_category_codes
            ]
        )

        existing_labels = set(
            await session.execute(select(SectorLabelRow.sector_code, SectorLabelRow.language))
        )
        session.add_all(
            [
                SectorLabelRow(
                    sector_code=definition.code,
                    language=language,
                    label=label,
                    normalized_label=_normalize_search_text(label),
                    source="atlas-sector-registry",
                    review_status="approved",
                )
                for definition in SECTOR_REGISTRY
                for language, label in (("en", definition.name_en), ("tr", definition.name_tr))
                if (definition.code, language) not in existing_labels
            ]
        )

    async def list_countries(self, *, language: str = "en") -> list[dict[str, Any]]:
        requested_language = language.casefold()
        async with self._sessions() as session:
            countries = (
                await session.execute(
                    select(CountryRow)
                    .where(CountryRow.active.is_(True))
                    .order_by(CountryRow.canonical_name)
                )
            ).scalars()
            country_rows = list(countries)
            labels = (
                await session.execute(
                    select(CountryLabelRow).where(
                        CountryLabelRow.country_code.in_(row.code for row in country_rows),
                        CountryLabelRow.review_status == "approved",
                        CountryLabelRow.language.in_((requested_language, "en")),
                        CountryLabelRow.label_type.in_(("canonical", "official", "common")),
                    )
                )
            ).scalars()
            preferred: dict[tuple[str, str], CountryLabelRow] = {}
            type_rank = {"canonical": 0, "common": 1, "official": 2}
            for label in labels:
                key = (label.country_code, label.language)
                current = preferred.get(key)
                if current is None or type_rank.get(label.label_type, 9) < type_rank.get(
                    current.label_type, 9
                ):
                    preferred[key] = label
        payload: list[dict[str, Any]] = []
        for row in country_rows:
            selected_label = preferred.get((row.code, requested_language)) or preferred.get(
                (row.code, "en")
            )
            payload.append(
                {
                    "code": row.code,
                    "alpha3": row.alpha3,
                    "numeric_code": row.numeric_code,
                    "name": selected_label.label if selected_label else row.canonical_name,
                    "canonical_name": row.canonical_name,
                    "registry_version": row.registry_version,
                }
            )
        return sorted(
            payload,
            key=lambda item: (str(item["name"]).casefold(), str(item["code"])),
        )

    async def resolve_country_code(self, value: str) -> dict[str, Any] | None:
        normalized = _normalize_country_text(value)
        if not normalized:
            return None
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(CountryLabelRow, CountryRow)
                    .join(CountryRow, CountryRow.code == CountryLabelRow.country_code)
                    .where(
                        CountryRow.active.is_(True),
                        CountryLabelRow.review_status == "approved",
                        CountryLabelRow.normalized_label == normalized,
                    )
                )
            ).all()
        codes = {country.code for _, country in rows}
        if len(codes) != 1:
            return None
        label, country = min(
            rows,
            key=lambda item: (
                0 if item[0].label_type == "canonical" else 1,
                item[0].language != "en",
            ),
        )
        return {
            "code": country.code,
            "alpha3": country.alpha3,
            "name": country.canonical_name,
            "matched_alias": label.label,
        }

    async def resolve_country_query(self, query: str) -> dict[str, Any] | None:
        word_matches = list(re.finditer(r"\w+", query, flags=re.UNICODE))
        tokens = [_normalize_country_text(match.group()) for match in word_matches]
        if not tokens:
            return None
        phrases: dict[str, tuple[int, int]] = {}
        for start in range(len(tokens)):
            for end in range(start + 1, min(len(tokens), start + 7) + 1):
                phrases[" ".join(tokens[start:end])] = (start, end)
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(CountryLabelRow, CountryRow)
                    .join(CountryRow, CountryRow.code == CountryLabelRow.country_code)
                    .where(
                        CountryRow.active.is_(True),
                        CountryLabelRow.review_status == "approved",
                        CountryLabelRow.normalized_label.in_(tuple(phrases)),
                    )
                )
            ).all()
        ambiguous_codes = {"am", "as", "at", "do", "in", "is", "it", "me", "no", "to"}
        candidates: list[tuple[int, int, CountryLabelRow, CountryRow]] = []
        raw_tokens = [match.group() for match in word_matches]
        for label, country in rows:
            start, end = phrases[label.normalized_label]
            if (
                label.label_type == "code"
                and label.normalized_label in ambiguous_codes
                and not any(
                    token == token.upper() and token.casefold() == label.normalized_label
                    for token in raw_tokens
                )
            ):
                continue
            candidates.append((start, end, label, country))
        if not candidates:
            return None
        longest = max(end - start for start, end, _, _ in candidates)
        winners = [item for item in candidates if item[1] - item[0] == longest]
        winner_codes = {country.code for _, _, _, country in winners}
        if len(winner_codes) != 1:
            return None
        start, end, label, country = min(
            winners,
            key=lambda item: (
                item[0],
                0 if item[2].label_type in {"canonical", "common"} else 1,
            ),
        )
        search_query = re.sub(
            r"\s+",
            " ",
            f"{query[: word_matches[start].start()]} {query[word_matches[end - 1].end() :]}",
        ).strip(" ,;:-")
        return {
            "original_query": query,
            "search_query": search_query,
            "geography_code": country.code,
            "geography_name": country.canonical_name,
            "matched_alias": label.label,
        }

    async def sync_sources(self, sources: tuple[SourceDefinition, ...]) -> None:
        async with self._sessions.begin() as session:
            for definition in sources:
                license_row = await session.scalar(
                    select(LicenseRow).where(LicenseRow.name == definition.license.name)
                )
                license_payload = definition.license.model_dump(mode="json")
                if license_row is None:
                    license_row = LicenseRow(name=definition.license.name)
                    session.add(license_row)
                    await session.flush()
                for key, value in license_payload.items():
                    if key != "name":
                        setattr(license_row, key, value)

                source = await session.scalar(
                    select(SourceRow).where(SourceRow.code == definition.code)
                )
                payload = definition.model_dump(mode="json")
                if source is None:
                    source = SourceRow(
                        license_id=license_row.id,
                        code=definition.code,
                        name=definition.name,
                        publisher=definition.publisher,
                        country=definition.country,
                        region=definition.region,
                        status=definition.status.value,
                        health=definition.health.value,
                        schedule=definition.ingestion.schedule,
                        next_check_at=utc_now() if definition.status.value == "active" else None,
                        manifest=payload,
                    )
                    session.add(source)
                else:
                    source.license_id = license_row.id
                    source.name = definition.name
                    source.publisher = definition.publisher
                    source.country = definition.country
                    source.region = definition.region
                    source.status = definition.status.value
                    source.health = definition.health.value
                    source.schedule = definition.ingestion.schedule
                source.manifest = payload
                if definition.status.value == "active" and source.next_check_at is None:
                    source.next_check_at = utc_now()
                elif definition.status.value != "active":
                    source.next_check_at = None

    async def seed_intelligence(self, units: UnitEngine, semantics: SemanticRegistry) -> None:
        async with self._sessions.begin() as session:
            for definition in units.definitions():
                row = await session.scalar(
                    select(UnitDefinitionRow).where(UnitDefinitionRow.code == definition.code)
                )
                if row is None:
                    row = UnitDefinitionRow(
                        code=definition.code,
                        dimension=definition.dimension,
                        scale_to_base=definition.scale_to_base,
                        offset_to_base=definition.offset_to_base,
                        ucum_code=definition.ucum_code,
                        qualifiers=list(definition.qualifiers),
                        registry_version=units.version,
                        active=True,
                    )
                    session.add(row)
                    await session.flush()
                row.dimension = definition.dimension
                row.scale_to_base = definition.scale_to_base
                row.offset_to_base = definition.offset_to_base
                row.ucum_code = definition.ucum_code
                row.qualifiers = list(definition.qualifiers)
                row.registry_version = units.version
                row.active = True
                for alias in (definition.code, *definition.aliases):
                    normalized = " ".join(alias.strip().casefold().split())
                    alias_row = await session.scalar(
                        select(UnitAliasRow).where(
                            UnitAliasRow.normalized_alias == normalized,
                            UnitAliasRow.source_code.is_(None),
                        )
                    )
                    if alias_row is None:
                        session.add(
                            UnitAliasRow(
                                unit_definition_id=row.id,
                                alias=alias,
                                normalized_alias=normalized,
                                source_code=None,
                                language=None,
                                review_status="approved",
                                registry_version=units.version,
                            )
                        )

            for concept in semantics.concepts():
                concept_row = await session.scalar(
                    select(ConceptRow).where(ConceptRow.code == concept.code)
                )
                if concept_row is None:
                    concept_row = ConceptRow(
                        code=concept.code,
                        family=concept.family,
                        canonical_name_en=concept.canonical_name_en,
                        registry_version=semantics.version,
                        active=True,
                    )
                    session.add(concept_row)
                    await session.flush()
                concept_row.family = concept.family
                concept_row.canonical_name_en = concept.canonical_name_en
                concept_row.registry_version = semantics.version
                concept_row.active = True
                for label in concept.labels:
                    normalized = semantics.normalize(label.label)
                    label_row = await session.scalar(
                        select(ConceptLabelRow).where(
                            ConceptLabelRow.concept_id == concept_row.id,
                            ConceptLabelRow.language == label.language,
                            ConceptLabelRow.normalized_label == normalized,
                        )
                    )
                    if label_row is None:
                        label_row = ConceptLabelRow(
                            concept_id=concept_row.id,
                            language=label.language,
                            normalized_label=normalized,
                        )
                        session.add(label_row)
                    label_row.label = label.label
                    label_row.label_kind = label.kind
                    label_row.translation_method = label.method
                    label_row.translation_model = label.model
                    label_row.confidence = (
                        None if label.confidence is None else Decimal(str(label.confidence))
                    )
                    label_row.review_status = label.review_status
                    label_row.registry_version = semantics.version

    async def rebuild_intelligence_index(
        self, units: UnitEngine, semantics: SemanticRegistry
    ) -> dict[str, int]:
        await self.seed_intelligence(units, semantics)
        async with self._sessions.begin() as session:
            raw_units = (
                await session.execute(
                    text(
                        """
                        SELECT DISTINCT factor_unit AS raw_unit, 'factor_unit' AS layer
                        FROM atlas_factor_versions
                        UNION
                        SELECT DISTINCT activity_unit, 'activity_unit'
                        FROM atlas_factor_versions
                        UNION
                        SELECT DISTINCT unit, 'source_observation'
                        FROM atlas_source_observations
                        """
                    )
                )
            ).mappings()
            unit_mappings: list[dict[str, Any]] = []
            for row in raw_units:
                raw_unit = str(row["raw_unit"] or "")
                layer = str(row["layer"])
                mapping = units.classify(raw_unit, layer=layer)
                unit_mappings.append(
                    {
                        "id": uuid4(),
                        "layer": layer,
                        "raw_unit_hash": sha256(raw_unit.encode("utf-8")).hexdigest(),
                        "raw_unit": raw_unit,
                        "normalized_expression": mapping.normalized_expression,
                        "mapping_status": mapping.status.value,
                        "canonical_expression": mapping.canonical_expression,
                        "numerator_code": mapping.numerator_code,
                        "denominator_code": mapping.denominator_code,
                        "denominator_quantity": mapping.denominator_quantity,
                        "reason_code": mapping.reason_code,
                        "registry_version": units.version,
                    }
                )
            if unit_mappings:
                await session.execute(
                    text(
                        """
                        INSERT INTO atlas_unit_expression_mappings (
                          id, layer, raw_unit_hash, raw_unit, normalized_expression,
                          mapping_status, canonical_expression, numerator_code,
                          denominator_code, denominator_quantity, reason_code,
                          registry_version
                        ) VALUES (
                          :id, :layer, :raw_unit_hash, :raw_unit, :normalized_expression,
                          :mapping_status, :canonical_expression, :numerator_code,
                          :denominator_code, :denominator_quantity, :reason_code,
                          :registry_version
                        )
                        ON CONFLICT (layer, raw_unit_hash) DO UPDATE SET
                          raw_unit = EXCLUDED.raw_unit,
                          normalized_expression = EXCLUDED.normalized_expression,
                          mapping_status = EXCLUDED.mapping_status,
                          canonical_expression = EXCLUDED.canonical_expression,
                          numerator_code = EXCLUDED.numerator_code,
                          denominator_code = EXCLUDED.denominator_code,
                          denominator_quantity = EXCLUDED.denominator_quantity,
                          reason_code = EXCLUDED.reason_code,
                          registry_version = EXCLUDED.registry_version,
                          updated_at = now()
                        """
                    ),
                    unit_mappings,
                )
            await session.execute(
                text(
                    """
                    INSERT INTO atlas_factor_unit_expressions (
                      factor_version_id, numerator_code, denominator_code,
                      denominator_quantity, parse_status, reason, registry_version
                    )
                    SELECT fv.id, m.numerator_code, m.denominator_code,
                           m.denominator_quantity, m.mapping_status, m.reason_code, :version
                    FROM atlas_factor_versions fv
                    JOIN atlas_unit_expression_mappings m
                      ON m.layer = 'factor_unit' AND m.raw_unit = fv.factor_unit
                    ON CONFLICT (factor_version_id) DO UPDATE SET
                      numerator_code = EXCLUDED.numerator_code,
                      denominator_code = EXCLUDED.denominator_code,
                      denominator_quantity = EXCLUDED.denominator_quantity,
                      parse_status = EXCLUDED.parse_status,
                      reason = EXCLUDED.reason,
                      registry_version = EXCLUDED.registry_version
                    """
                ),
                {"version": units.version},
            )

            taxonomy_rows = (
                await session.execute(
                    text(
                        """
                        SELECT s.code AS source_code, fv.taxonomy_code,
                               min(fv.name) AS sample_name
                        FROM atlas_factor_versions fv
                        JOIN atlas_factors f ON f.id = fv.factor_id
                        JOIN atlas_sources s ON s.id = f.source_id
                        GROUP BY s.code, fv.taxonomy_code
                        ORDER BY s.code, fv.taxonomy_code
                        """
                    )
                )
            ).mappings()
            concept_mapping_rows: list[dict[str, Any]] = []
            for taxonomy in taxonomy_rows:
                source_code = str(taxonomy["source_code"])
                taxonomy_code = (
                    None if taxonomy["taxonomy_code"] is None else str(taxonomy["taxonomy_code"])
                )
                concept_code = _canonical_concept_code(taxonomy_code, source_code)
                concept_row = await session.scalar(
                    select(ConceptRow).where(ConceptRow.code == concept_code)
                )
                if concept_row is None:
                    canonical_name = _canonical_concept_name(
                        concept_code,
                        source_code=source_code,
                        sample_name=(
                            None
                            if taxonomy["sample_name"] is None
                            else str(taxonomy["sample_name"])
                        ),
                    )
                    concept_row = ConceptRow(
                        code=concept_code,
                        family=concept_code.split(".", 1)[0],
                        canonical_name_en=canonical_name,
                        registry_version=semantics.version,
                        active=True,
                    )
                    session.add(concept_row)
                    await session.flush()
                    session.add(
                        ConceptLabelRow(
                            concept_id=concept_row.id,
                            language="en",
                            label=canonical_name,
                            normalized_label=_normalize_search_text(canonical_name),
                            label_kind="canonical",
                            translation_method="generated_taxonomy",
                            translation_model=None,
                            confidence=Decimal("1"),
                            review_status="approved",
                            registry_version=semantics.version,
                        )
                    )
                concept_mapping_rows.append(
                    {
                        "source_code": source_code,
                        "taxonomy_code": taxonomy_code or "",
                        "concept_id": concept_row.id,
                    }
                )

            await session.execute(
                text(
                    """
                    CREATE TEMP TABLE atlas_concept_mapping_tmp (
                      source_code VARCHAR(64) NOT NULL,
                      taxonomy_code TEXT NOT NULL,
                      concept_id UUID NOT NULL,
                      PRIMARY KEY (source_code, taxonomy_code)
                    ) ON COMMIT DROP
                    """
                )
            )
            if concept_mapping_rows:
                await session.execute(
                    text(
                        """
                        INSERT INTO atlas_concept_mapping_tmp (
                          source_code, taxonomy_code, concept_id
                        ) VALUES (:source_code, :taxonomy_code, :concept_id)
                        """
                    ),
                    concept_mapping_rows,
                )
                await session.execute(
                    text(
                        """
                        INSERT INTO atlas_factor_concepts (
                          factor_id, concept_id, relation, mapping_version, review_status
                        )
                        SELECT DISTINCT f.id, m.concept_id, 'taxonomy', :version, 'approved'
                        FROM atlas_factors f
                        JOIN atlas_sources s ON s.id = f.source_id
                        JOIN atlas_factor_versions fv ON fv.factor_id = f.id
                        JOIN atlas_concept_mapping_tmp m
                          ON m.source_code = s.code
                         AND m.taxonomy_code = coalesce(fv.taxonomy_code, '')
                        ON CONFLICT (factor_id, concept_id) DO UPDATE SET
                          relation = EXCLUDED.relation,
                          mapping_version = EXCLUDED.mapping_version,
                          review_status = EXCLUDED.review_status
                        """
                    ),
                    {"version": semantics.version},
                )

            concept_rows = {row.code: row for row in await session.scalars(select(ConceptRow))}
            for concept in semantics.concepts():
                patterns = [
                    f"%{label.label}%"
                    for label in concept.labels
                    if label.review_status == "approved"
                ]
                if not patterns:
                    continue
                await session.execute(
                    text(
                        """
                        INSERT INTO atlas_factor_concepts (
                          factor_id, concept_id, relation, mapping_version, review_status
                        )
                        SELECT DISTINCT f.id, :concept_id, 'primary', :version, 'approved'
                        FROM atlas_factors f
                        JOIN atlas_factor_versions fv ON fv.factor_id = f.id
                        WHERE fv.version_status = 'current'
                          AND concat_ws(' ', fv.name, fv.taxonomy_code, fv.activity_type)
                              ILIKE ANY(CAST(:patterns AS text[]))
                        ON CONFLICT (factor_id, concept_id) DO UPDATE SET
                          mapping_version = EXCLUDED.mapping_version,
                          review_status = EXCLUDED.review_status
                        """
                    ),
                    {
                        "concept_id": concept_rows[concept.code].id,
                        "version": semantics.version,
                        "patterns": patterns,
                    },
                )

            parsed = int(
                await session.scalar(
                    select(func.count())
                    .select_from(FactorUnitExpressionRow)
                    .where(FactorUnitExpressionRow.parse_status == "mapped")
                )
                or 0
            )
            unparsed = int(
                await session.scalar(
                    select(func.count())
                    .select_from(FactorUnitExpressionRow)
                    .where(FactorUnitExpressionRow.parse_status == "unparsed")
                )
                or 0
            )
            unit_expressions_classified = int(
                await session.scalar(select(func.count()).select_from(UnitExpressionMappingRow))
                or 0
            )
            source_native = int(
                await session.scalar(
                    select(func.count())
                    .select_from(UnitExpressionMappingRow)
                    .where(UnitExpressionMappingRow.mapping_status == "source_native")
                )
                or 0
            )
            mapped = int(
                await session.scalar(select(func.count()).select_from(FactorConceptRow)) or 0
            )
            factors_without_concept = int(
                await session.scalar(
                    text(
                        """
                        SELECT count(*)
                        FROM atlas_factors f
                        WHERE NOT EXISTS (
                          SELECT 1 FROM atlas_factor_concepts fc
                          WHERE fc.factor_id = f.id AND fc.review_status = 'approved'
                        )
                        """
                    )
                )
                or 0
            )
        return {
            "factor_units_mapped": parsed,
            "factor_units_unparsed": unparsed,
            "unit_expressions_classified": unit_expressions_classified,
            "unit_expressions_source_native": source_native,
            "factor_concepts_mapped": mapped,
            "factors_without_concept": factors_without_concept,
        }

    async def unit_inventory(self) -> list[dict[str, Any]]:
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    text(
                        """
                        WITH inventory AS (
                          SELECT factor_unit AS raw_unit, 'factor_unit' AS layer,
                                 COUNT(*) AS occurrences
                          FROM atlas_factor_versions GROUP BY factor_unit
                          UNION ALL
                          SELECT activity_unit, 'activity_unit', COUNT(*)
                          FROM atlas_factor_versions GROUP BY activity_unit
                          UNION ALL
                          SELECT unit, 'source_observation', COUNT(*)
                          FROM atlas_source_observations GROUP BY unit
                        )
                        SELECT i.raw_unit, i.layer, i.occurrences::bigint,
                               m.normalized_expression, m.mapping_status,
                               m.canonical_expression, m.reason_code,
                               m.registry_version
                        FROM inventory i
                        LEFT JOIN atlas_unit_expression_mappings m
                          ON m.layer = i.layer AND m.raw_unit = i.raw_unit
                        ORDER BY i.occurrences DESC, i.raw_unit, i.layer
                        """
                    )
                )
            ).mappings()
            return [dict(row) for row in rows]

    async def intelligence_coverage(self, *, target_languages: tuple[str, ...]) -> dict[str, Any]:
        async with self._sessions() as session:
            unit_rows = (
                await session.execute(
                    text(
                        """
                        SELECT layer, mapping_status, count(*)::bigint AS expressions
                        FROM atlas_unit_expression_mappings
                        GROUP BY layer, mapping_status
                        ORDER BY layer, mapping_status
                        """
                    )
                )
            ).mappings()
            inventory_total = int(
                await session.scalar(
                    text(
                        """
                        SELECT count(*) FROM (
                          SELECT factor_unit, 'factor_unit' FROM atlas_factor_versions
                          GROUP BY factor_unit
                          UNION
                          SELECT activity_unit, 'activity_unit' FROM atlas_factor_versions
                          GROUP BY activity_unit
                          UNION
                          SELECT unit, 'source_observation' FROM atlas_source_observations
                          GROUP BY unit
                        ) inventory
                        """
                    )
                )
                or 0
            )
            classified_total = int(
                await session.scalar(select(func.count()).select_from(UnitExpressionMappingRow))
                or 0
            )
            factor_total = int(
                await session.scalar(select(func.count()).select_from(FactorRow)) or 0
            )
            factors_mapped = int(
                await session.scalar(
                    select(func.count(func.distinct(FactorConceptRow.factor_id))).where(
                        FactorConceptRow.review_status == "approved"
                    )
                )
                or 0
            )
            calculation_units_unmapped = int(
                await session.scalar(
                    text(
                        """
                        SELECT count(*)
                        FROM atlas_factor_unit_expressions fue
                        JOIN atlas_factor_versions fv ON fv.id = fue.factor_version_id
                        WHERE fv.version_status = 'current'
                          AND (
                            (
                              fv.factor_value_kind = 'co2e_total'
                              AND fv.intended_use IN (
                                'inventory', 'calculation_input', 'characterization'
                              )
                            )
                            OR (
                              fv.factor_value_kind = 'characterization_factor'
                              AND fv.intended_use IN ('characterization', 'calculation_input')
                            )
                          )
                          AND fue.parse_status <> 'mapped'
                        """
                    )
                )
                or 0
            )
            concept_total = int(
                await session.scalar(
                    select(func.count()).select_from(ConceptRow).where(ConceptRow.active.is_(True))
                )
                or 0
            )
            translation_rows = (
                await session.execute(
                    select(
                        ConceptLabelRow.language,
                        ConceptLabelRow.review_status,
                        func.count(func.distinct(ConceptLabelRow.concept_id)),
                    )
                    .where(
                        ConceptLabelRow.language.in_(target_languages),
                        ConceptLabelRow.label_kind.in_(("canonical", "translation")),
                    )
                    .group_by(ConceptLabelRow.language, ConceptLabelRow.review_status)
                )
            ).all()
            coverage_by_language = {
                language: {"approved": 0, "draft": 0, "missing": concept_total}
                for language in target_languages
            }
            for language, review_status, covered in translation_rows:
                coverage_by_language[str(language)][str(review_status)] = int(covered)
            for values in coverage_by_language.values():
                values["missing"] = max(concept_total - values["approved"] - values["draft"], 0)
            missing_approved_labels = sum(
                max(concept_total - values["approved"], 0)
                for values in coverage_by_language.values()
            )
            gates = {
                "unit_inventory_complete": classified_total == inventory_total,
                "calculation_unit_coverage_complete": calculation_units_unmapped == 0,
                "factor_concept_coverage_complete": factors_mapped == factor_total,
                "approved_translation_coverage_complete": missing_approved_labels == 0,
            }
            return {
                "ready": all(gates.values()),
                "gates": gates,
                "units": {
                    "inventory_total": inventory_total,
                    "classified_total": classified_total,
                    "calculation_eligible_unmapped_versions": calculation_units_unmapped,
                    "by_layer_and_status": [dict(row) for row in unit_rows],
                },
                "semantics": {
                    "factors_total": factor_total,
                    "factors_with_approved_concept": factors_mapped,
                    "concepts_total": concept_total,
                    "languages": coverage_by_language,
                },
            }

    async def list_concepts(self, *, language: str | None = None) -> list[dict[str, Any]]:
        async with self._sessions() as session:
            statement = (
                select(ConceptRow, ConceptLabelRow)
                .join(ConceptLabelRow, ConceptLabelRow.concept_id == ConceptRow.id)
                .where(ConceptRow.active.is_(True))
                .order_by(ConceptRow.code, ConceptLabelRow.language, ConceptLabelRow.label)
            )
            if language:
                statement = statement.where(ConceptLabelRow.language == language)
            rows = (await session.execute(statement)).all()
            concepts: dict[str, dict[str, Any]] = {}
            for concept, label in rows:
                item = concepts.setdefault(
                    concept.code,
                    {
                        "code": concept.code,
                        "family": concept.family,
                        "canonical_name_en": concept.canonical_name_en,
                        "registry_version": concept.registry_version,
                        "labels": [],
                    },
                )
                item["labels"].append(
                    {
                        "language": label.language,
                        "label": label.label,
                        "definition": label.definition,
                        "kind": label.label_kind,
                        "is_preferred": label.is_preferred,
                        "term_source": label.term_source,
                        "method": label.translation_method,
                        "model": label.translation_model,
                        "confidence": label.confidence,
                        "review_status": label.review_status,
                        "reviewed_by": label.reviewed_by,
                        "reviewed_at": label.reviewed_at,
                        "review_note": label.review_note,
                        "qa_flags": label.qa_flags,
                        "prompt_version": label.prompt_version,
                        "glossary_version": label.glossary_version,
                        "registry_version": label.registry_version,
                    }
                )
            return list(concepts.values())

    async def generate_missing_concept_translations(
        self,
        translator: DraftTranslator,
        *,
        target_languages: tuple[str, ...],
    ) -> dict[str, int]:
        async with self._sessions.begin() as session:
            concepts = tuple(
                await session.scalars(
                    select(ConceptRow).where(ConceptRow.active.is_(True)).order_by(ConceptRow.code)
                )
            )
            existing_rows = (
                await session.execute(
                    select(ConceptLabelRow.concept_id, ConceptLabelRow.language).where(
                        ConceptLabelRow.language.in_(target_languages)
                    )
                )
            ).all()
            existing = {(concept_id, language) for concept_id, language in existing_rows}
            generated = 0
            for language in target_languages:
                if language == "en":
                    continue
                for concept in concepts:
                    if (concept.id, language) in existing:
                        continue
                    label = translator.draft(concept.canonical_name_en, "en", language)
                    session.add(
                        ConceptLabelRow(
                            concept_id=concept.id,
                            language=language,
                            label=label.label,
                            normalized_label=_normalize_search_text(label.label),
                            label_kind=label.kind,
                            translation_method=label.method,
                            translation_model=label.model,
                            confidence=None,
                            review_status=label.review_status,
                            registry_version=concept.registry_version,
                        )
                    )
                    generated += 1
            return {"concepts": len(concepts), "translations_generated": generated}

    async def translation_reviews(
        self,
        *,
        review_status: str = "draft",
        language: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        async with self._sessions() as session:
            statement = (
                select(ConceptLabelRow, ConceptRow)
                .join(ConceptRow, ConceptRow.id == ConceptLabelRow.concept_id)
                .where(ConceptLabelRow.review_status == review_status)
                .order_by(ConceptLabelRow.language, ConceptRow.code, ConceptLabelRow.label)
                .limit(limit)
                .offset(offset)
            )
            if language:
                statement = statement.where(ConceptLabelRow.language == language)
            rows = (await session.execute(statement)).all()
            return [
                {
                    "label_id": str(label.id),
                    "concept_code": concept.code,
                    "canonical_name_en": concept.canonical_name_en,
                    "language": label.language,
                    "label": label.label,
                    "definition": label.definition,
                    "kind": label.label_kind,
                    "is_preferred": label.is_preferred,
                    "term_source": label.term_source,
                    "method": label.translation_method,
                    "model": label.translation_model,
                    "confidence": label.confidence,
                    "review_status": label.review_status,
                    "reviewed_by": label.reviewed_by,
                    "reviewed_at": label.reviewed_at,
                    "review_note": label.review_note,
                    "qa_flags": label.qa_flags,
                    "prompt_version": label.prompt_version,
                    "glossary_version": label.glossary_version,
                    "registry_version": label.registry_version,
                }
                for label, concept in rows
            ]

    async def decide_translation_review(
        self,
        label_id: UUID,
        *,
        decision: str,
        reviewed_by: str,
        note: str | None,
    ) -> dict[str, Any]:
        if decision not in {"approved", "rejected"}:
            raise ValueError(f"unknown translation review decision: {decision}")
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(ConceptLabelRow).where(ConceptLabelRow.id == label_id)
            )
            if row is None:
                raise LookupError(f"unknown concept label: {label_id}")
            if row.translation_method not in {"openai", "argos", "manual"}:
                raise ValueError(f"concept label is not reviewable: {label_id}")
            if decision == "approved" and row.is_preferred:
                current = tuple(
                    await session.scalars(
                        select(ConceptLabelRow).where(
                            ConceptLabelRow.concept_id == row.concept_id,
                            ConceptLabelRow.language == row.language,
                            ConceptLabelRow.is_preferred.is_(True),
                            ConceptLabelRow.review_status == "approved",
                            ConceptLabelRow.id != row.id,
                        )
                    )
                )
                for previous in current:
                    previous.review_status = "superseded"
                    previous.reviewed_by = reviewed_by
                    previous.reviewed_at = utc_now()
                    previous.review_note = f"Superseded by {row.id}"
                    row.supersedes_id = previous.id
                if current:
                    await session.flush()
            row.review_status = decision
            row.reviewed_by = reviewed_by
            row.reviewed_at = utc_now()
            row.review_note = note
            if decision == "approved" and row.language == "en" and row.is_preferred:
                concept = await session.scalar(
                    select(ConceptRow).where(ConceptRow.id == row.concept_id)
                )
                if concept is not None:
                    concept.canonical_name_en = row.label
                    concept.definition_en = row.definition
                    concept.english_review_status = "approved"
                    concept.english_reviewed_by = reviewed_by
                    concept.english_reviewed_at = row.reviewed_at
            return {
                "label_id": str(row.id),
                "decision": decision,
                "reviewed_by": reviewed_by,
                "reviewed_at": row.reviewed_at,
                "review_note": note,
            }

    async def approve_translation_rollout(
        self,
        language: str,
        *,
        reviewed_by: str,
        note: str | None,
    ) -> dict[str, Any]:
        """Approve one generated language rollout with one preferred label per concept."""

        async with self._sessions.begin() as session:
            concepts = tuple(
                await session.scalars(
                    select(ConceptRow).where(ConceptRow.active.is_(True)).order_by(ConceptRow.code)
                )
            )
            concept_ids = tuple(concept.id for concept in concepts)
            rows = list(
                await session.scalars(
                    select(ConceptLabelRow).where(
                        ConceptLabelRow.concept_id.in_(concept_ids),
                        ConceptLabelRow.language == language,
                        ConceptLabelRow.review_status == "draft",
                        ConceptLabelRow.translation_method.in_(("openai", "manual")),
                    )
                )
            )
            by_concept: dict[UUID, list[ConceptLabelRow]] = {}
            for row in rows:
                by_concept.setdefault(row.concept_id, []).append(row)

            approved = 0
            rejected = 0
            redundant = 0
            existing_preferred_superseded = 0
            concepts_reviewed = 0
            warnings_acknowledged = 0
            missing_preferred: list[str] = []
            now = utc_now()
            review_note = note or "Owner-delegated terminology rollout review"

            for concept in concepts:
                candidates = by_concept.get(concept.id, [])
                preferred = [row for row in candidates if row.is_preferred]
                if not preferred:
                    existing = list(
                        await session.scalars(
                            select(ConceptLabelRow).where(
                                ConceptLabelRow.concept_id == concept.id,
                                ConceptLabelRow.language == language,
                                ConceptLabelRow.is_preferred.is_(True),
                                ConceptLabelRow.review_status == "approved",
                            )
                        )
                    )
                    if not existing:
                        missing_preferred.append(concept.code)
                        continue

                    method_priority = {
                        "manual": 0,
                        "curated": 1,
                        "openai": 2,
                        "generated_taxonomy": 3,
                        "argos": 4,
                    }
                    canonical_name = concept.canonical_name_en.casefold()

                    def existing_preference_key(
                        row: ConceptLabelRow,
                        canonical_name: str = canonical_name,
                        method_priority: dict[str, int] = method_priority,
                    ) -> tuple[int, int, int, str]:
                        canonical_match = language == "en" and (
                            row.label.casefold() == canonical_name
                        )
                        return (
                            0 if canonical_match else 1,
                            method_priority.get(row.translation_method, 5),
                            len(row.qa_flags),
                            row.label.casefold(),
                        )

                    winner = min(existing, key=existing_preference_key)
                    for duplicate in existing:
                        if duplicate.id == winner.id:
                            continue
                        duplicate.review_status = "superseded"
                        duplicate.reviewed_by = reviewed_by
                        duplicate.reviewed_at = now
                        duplicate.review_note = (
                            f"Duplicate approved preferred label; retained {winner.id}"
                        )
                        existing_preferred_superseded += 1

                    if language == "en" and concept.english_review_status != "approved":
                        concept.canonical_name_en = winner.label
                        concept.definition_en = winner.definition
                        concept.english_review_status = "approved"
                        concept.english_reviewed_by = reviewed_by
                        concept.english_reviewed_at = now
                        concepts_reviewed += 1
                    continue

                def preference_key(row: ConceptLabelRow) -> tuple[int, int, int, str]:
                    hard_flags = {"repeated_token", "term_too_long"}.intersection(row.qa_flags)
                    return (
                        len(hard_flags),
                        0 if row.translation_method == "manual" else 1,
                        len(row.qa_flags),
                        row.label.casefold(),
                    )

                winner = min(preferred, key=preference_key)
                current_preferred = tuple(
                    await session.scalars(
                        select(ConceptLabelRow).where(
                            ConceptLabelRow.concept_id == concept.id,
                            ConceptLabelRow.language == language,
                            or_(
                                ConceptLabelRow.is_preferred.is_(True),
                                ConceptLabelRow.normalized_label == winner.normalized_label,
                            ),
                            ConceptLabelRow.review_status == "approved",
                            ConceptLabelRow.id != winner.id,
                        )
                    )
                )
                for previous in current_preferred:
                    previous.review_status = "superseded"
                    previous.reviewed_by = reviewed_by
                    previous.reviewed_at = now
                    previous.review_note = f"Superseded by rollout label {winner.id}"
                    winner.supersedes_id = previous.id
                if current_preferred:
                    await session.flush()

                for candidate in preferred:
                    if candidate.id == winner.id:
                        continue
                    candidate.review_status = "rejected"
                    candidate.reviewed_by = reviewed_by
                    candidate.reviewed_at = now
                    candidate.review_note = f"Duplicate preferred draft; selected {winner.id}"
                    rejected += 1

                winner.review_status = "approved"
                winner.reviewed_by = reviewed_by
                winner.reviewed_at = now
                winner.review_note = review_note
                warnings_acknowledged += bool(winner.qa_flags)
                approved += 1
                if language == "en":
                    concept.canonical_name_en = winner.label
                    concept.definition_en = winner.definition
                    concept.english_review_status = "approved"
                    concept.english_reviewed_by = reviewed_by
                    concept.english_reviewed_at = now

            await session.flush()
            for row in rows:
                if row.is_preferred or row.review_status != "draft":
                    continue
                collision = await session.scalar(
                    select(ConceptLabelRow).where(
                        ConceptLabelRow.concept_id == row.concept_id,
                        ConceptLabelRow.language == language,
                        ConceptLabelRow.normalized_label == row.normalized_label,
                        ConceptLabelRow.review_status == "approved",
                        ConceptLabelRow.id != row.id,
                    )
                )
                if collision is not None:
                    row.review_status = "superseded"
                    row.reviewed_by = reviewed_by
                    row.reviewed_at = now
                    row.review_note = f"Equivalent approved label {collision.id} already exists"
                    redundant += 1
                    continue
                row.review_status = "approved"
                row.reviewed_by = reviewed_by
                row.reviewed_at = now
                row.review_note = review_note
                warnings_acknowledged += bool(row.qa_flags)
                approved += 1

            if missing_preferred:
                raise ValueError(
                    f"{language} rollout has {len(missing_preferred)} concepts without an "
                    f"approved or draft preferred label: {missing_preferred[:10]}"
                )
            return {
                "language": language,
                "concepts": len(concepts),
                "approved": approved,
                "rejected_duplicate_preferred": rejected,
                "redundant_existing": redundant,
                "existing_preferred_superseded": existing_preferred_superseded,
                "concepts_reviewed": concepts_reviewed,
                "warnings_acknowledged": warnings_acknowledged,
                "reviewed_by": reviewed_by,
                "reviewed_at": now,
            }

    async def upsert_concept_label(
        self,
        concept_code: str,
        label: ConceptLabel,
        *,
        registry_version: str,
    ) -> dict[str, Any]:
        async with self._sessions.begin() as session:
            concept = await session.scalar(
                select(ConceptRow).where(ConceptRow.code == concept_code)
            )
            if concept is None:
                raise LookupError(f"unknown canonical concept: {concept_code}")
            normalized = _normalize_search_text(label.label)
            row = await session.scalar(
                select(ConceptLabelRow).where(
                    ConceptLabelRow.concept_id == concept.id,
                    ConceptLabelRow.language == label.language,
                    ConceptLabelRow.normalized_label == normalized,
                )
            )
            if row is None:
                row = ConceptLabelRow(
                    concept_id=concept.id,
                    language=label.language,
                    normalized_label=normalized,
                )
                session.add(row)
            row.label = label.label
            row.definition = None
            row.label_kind = label.kind
            row.is_preferred = label.kind in {"canonical", "translation"}
            row.term_source = label.method
            row.translation_method = label.method
            row.translation_model = label.model
            row.confidence = None if label.confidence is None else Decimal(str(label.confidence))
            row.review_status = label.review_status
            row.registry_version = registry_version
            return {
                **label.model_dump(mode="json"),
                "concept_code": concept_code,
                "registry_version": registry_version,
            }

    async def edit_translation_draft(
        self,
        label_id: UUID,
        *,
        label: str,
        definition: str | None,
    ) -> dict[str, Any]:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(ConceptLabelRow).where(ConceptLabelRow.id == label_id)
            )
            if row is None:
                raise LookupError(f"unknown concept label: {label_id}")
            if row.review_status != "draft":
                raise ValueError("only draft terminology can be edited")
            normalized = _normalize_search_text(label)
            collision = await session.scalar(
                select(ConceptLabelRow.id).where(
                    ConceptLabelRow.concept_id == row.concept_id,
                    ConceptLabelRow.language == row.language,
                    ConceptLabelRow.normalized_label == normalized,
                    ConceptLabelRow.id != row.id,
                )
            )
            if collision is not None:
                raise ValueError("an equivalent concept label already exists")
            row.label = label
            row.definition = definition
            row.normalized_label = normalized
            row.tokens = normalized.split()
            row.qa_flags = []
            row.translation_method = "manual"
            row.term_source = "manual_review"
            return {
                "label_id": str(row.id),
                "label": row.label,
                "definition": row.definition,
                "review_status": row.review_status,
                "method": row.translation_method,
            }

    async def resolve_concepts(
        self,
        query: str,
        *,
        language: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        from atlas.semantics import MultilingualConceptResolver, ResolvableTerm

        normalized_query = _normalize_search_text(query)
        async with self._sessions() as session:
            base_statement = (
                select(ConceptRow, ConceptLabelRow)
                .join(ConceptLabelRow, ConceptLabelRow.concept_id == ConceptRow.id)
                .where(
                    ConceptRow.active.is_(True),
                    ConceptLabelRow.review_status == "approved",
                )
            )
            rows = (
                await session.execute(
                    base_statement.where(
                        ConceptLabelRow.normalized_label == normalized_query
                    )
                )
            ).all()
            if not rows and normalized_query:
                # pg_trgm narrows fuzzy matching to a small indexed candidate set.
                # Scoring every approved label made recommendation latency scale with
                # the entire multilingual terminology catalog.
                rows = (
                    await session.execute(
                        base_statement.where(
                            ConceptLabelRow.normalized_label.op("%")(
                                normalized_query
                            )
                        )
                        .order_by(
                            func.similarity(
                                ConceptLabelRow.normalized_label,
                                normalized_query,
                            ).desc()
                        )
                        .limit(max(100, limit * 20))
                    )
                ).all()
        terms = [
            ResolvableTerm(
                concept_code=concept.code,
                family=concept.family,
                language=label.language,
                term=label.label,
                kind=label.label_kind,
                is_preferred=label.is_preferred,
            )
            for concept, label in rows
        ]
        return (
            MultilingualConceptResolver()
            .resolve(query, terms, language=language, limit=limit)
            .model_dump(mode="json")
        )

    async def translation_inputs(
        self,
        *,
        target_language: str,
        only_missing: bool = True,
    ) -> list[TranslationInput]:
        from atlas.semantics import TranslationInput

        async with self._sessions() as session:
            concepts = tuple(
                await session.scalars(
                    select(ConceptRow).where(ConceptRow.active.is_(True)).order_by(ConceptRow.code)
                )
            )
            existing: set[UUID] = set()
            queued_concept_codes: set[str] = set()
            if only_missing:
                existing = set(
                    await session.scalars(
                        select(ConceptLabelRow.concept_id).where(
                            ConceptLabelRow.language == target_language,
                            ConceptLabelRow.is_preferred.is_(True),
                            ConceptLabelRow.review_status.in_(("draft", "approved")),
                            ConceptLabelRow.translation_method.in_(("openai", "manual")),
                        )
                    )
                )
                active_jobs = tuple(
                    await session.scalars(
                        select(TranslationJobRow).where(
                            TranslationJobRow.target_language == target_language,
                            TranslationJobRow.status.in_(
                                (
                                    "created",
                                    "submitted",
                                    "validating",
                                    "in_progress",
                                    "finalizing",
                                    "completed",
                                )
                            ),
                        )
                    )
                )
                for job in active_jobs:
                    queued_concept_codes.update(job.custom_ids.values())
            factor_rows = (
                await session.execute(
                    select(
                        FactorConceptRow.concept_id,
                        FactorVersionRow.name,
                        FactorVersionRow.activity_type,
                    )
                    .join(FactorRow, FactorRow.id == FactorConceptRow.factor_id)
                    .join(FactorVersionRow, FactorVersionRow.factor_id == FactorRow.id)
                    .where(FactorVersionRow.version_status == TemporalVersionStatus.CURRENT.value)
                    .order_by(FactorConceptRow.concept_id, FactorVersionRow.reference_year.desc())
                )
            ).all()
        samples: dict[UUID, list[str]] = {}
        activities: dict[UUID, set[str]] = {}
        for concept_id, name, activity_type in factor_rows:
            bucket = samples.setdefault(concept_id, [])
            if name and name not in bucket and len(bucket) < 5:
                bucket.append(str(name))
            if activity_type:
                activities.setdefault(concept_id, set()).add(str(activity_type))
        return [
            TranslationInput(
                concept_code=concept.code,
                family=concept.family,
                canonical_name_en=concept.canonical_name_en,
                definition_en=concept.definition_en,
                taxonomy_path=concept.code,
                sample_factor_names=tuple(samples.get(concept.id, [])),
                activity_types=tuple(sorted(activities.get(concept.id, set()))),
            )
            for concept in concepts
            if concept.id not in existing and concept.code not in queued_concept_codes
        ]

    async def glossary_terms(self, *, target_language: str) -> tuple[str, ...]:
        async with self._sessions() as session:
            rows = tuple(
                await session.scalars(
                    select(GlossaryEntryRow).where(
                        GlossaryEntryRow.target_language == target_language,
                        GlossaryEntryRow.review_status == "approved",
                    )
                )
            )
        return tuple(
            f"{row.source_term} -> {row.target_term}"
            if row.target_term
            else f"PRESERVE: {row.source_term}"
            for row in rows
        )

    async def glossary_version(self, *, target_language: str) -> str:
        async with self._sessions() as session:
            rows = tuple(
                await session.scalars(
                    select(GlossaryEntryRow)
                    .where(
                        GlossaryEntryRow.target_language == target_language,
                        GlossaryEntryRow.review_status == "approved",
                    )
                    .order_by(
                        GlossaryEntryRow.domain,
                        GlossaryEntryRow.source_term,
                    )
                )
            )
        snapshot = [
            {
                "source_term": row.source_term,
                "target_term": row.target_term,
                "domain": row.domain,
                "protected": row.protected,
                "version": row.version,
            }
            for row in rows
        ]
        payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return sha256(payload.encode("utf-8")).hexdigest()

    async def list_glossary(self, *, target_language: str | None = None) -> list[dict[str, Any]]:
        async with self._sessions() as session:
            statement = select(GlossaryEntryRow).order_by(
                GlossaryEntryRow.target_language, GlossaryEntryRow.source_term
            )
            if target_language:
                statement = statement.where(GlossaryEntryRow.target_language == target_language)
            rows = tuple(await session.scalars(statement))
        return [
            {
                "id": str(row.id),
                "source_term": row.source_term,
                "target_language": row.target_language,
                "target_term": row.target_term,
                "domain": row.domain,
                "protected": row.protected,
                "review_status": row.review_status,
                "version": row.version,
            }
            for row in rows
        ]

    async def upsert_glossary_entry(
        self,
        *,
        source_term: str,
        target_language: str,
        target_term: str | None,
        domain: str,
        protected: bool,
        version: str,
    ) -> dict[str, Any]:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(GlossaryEntryRow).where(
                    GlossaryEntryRow.source_term == source_term,
                    GlossaryEntryRow.target_language == target_language,
                    GlossaryEntryRow.domain == domain,
                )
            )
            if row is None:
                row = GlossaryEntryRow(
                    source_term=source_term,
                    target_language=target_language,
                    domain=domain,
                    version=version,
                )
                session.add(row)
            row.target_term = target_term
            row.protected = protected
            row.review_status = "approved"
            row.version = version
            await session.flush()
            return {
                "id": str(row.id),
                "source_term": row.source_term,
                "target_language": row.target_language,
                "target_term": row.target_term,
                "domain": row.domain,
                "protected": row.protected,
                "review_status": row.review_status,
                "version": row.version,
            }

    async def create_translation_job(
        self,
        *,
        provider_job_id: str,
        input_file_id: str,
        target_language: str,
        model: str,
        qa_model: str,
        prompt_version: str,
        glossary_version: str,
        custom_ids: dict[str, str],
        requested_by: str,
    ) -> dict[str, Any]:
        async with self._sessions.begin() as session:
            row = TranslationJobRow(
                provider="openai",
                provider_job_id=provider_job_id,
                input_file_id=input_file_id,
                source_language="en",
                target_language=target_language,
                model=model,
                qa_model=qa_model,
                prompt_version=prompt_version,
                glossary_version=glossary_version,
                status="submitted",
                requested_count=len(custom_ids),
                custom_ids=custom_ids,
                requested_by=requested_by,
            )
            session.add(row)
            await session.flush()
            return self._translation_job_payload(row)

    async def translation_jobs(self, *, limit: int = 100) -> list[dict[str, Any]]:
        async with self._sessions() as session:
            rows = tuple(
                await session.scalars(
                    select(TranslationJobRow)
                    .order_by(TranslationJobRow.created_at.desc())
                    .limit(limit)
                )
            )
        return [self._translation_job_payload(row) for row in rows]

    async def get_translation_job(self, job_id: UUID) -> dict[str, Any] | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(TranslationJobRow).where(TranslationJobRow.id == job_id)
            )
            return self._translation_job_payload(row) if row is not None else None

    async def update_translation_job(
        self,
        job_id: UUID,
        *,
        status: str,
        output_file_id: str | None = None,
        error_file_id: str | None = None,
        completed_count: int = 0,
        failed_count: int = 0,
        error: str | None = None,
    ) -> dict[str, Any]:
        async with self._sessions.begin() as session:
            row = await session.scalar(
                select(TranslationJobRow).where(TranslationJobRow.id == job_id)
            )
            if row is None:
                raise LookupError(f"unknown translation job: {job_id}")
            row.status = status
            row.output_file_id = output_file_id or row.output_file_id
            row.error_file_id = error_file_id or row.error_file_id
            row.completed_count = completed_count
            row.failed_count = failed_count
            row.error = error
            row.updated_at = utc_now()
            return self._translation_job_payload(row)

    async def ingest_translation_results(
        self,
        job_id: UUID,
        results: dict[str, TranslationDraft],
    ) -> dict[str, int]:
        from atlas.semantics import MultilingualConceptResolver

        async with self._sessions.begin() as session:
            job = await session.scalar(
                select(TranslationJobRow).where(TranslationJobRow.id == job_id)
            )
            if job is None:
                raise LookupError(f"unknown translation job: {job_id}")
            concepts = {
                row.code: row
                for row in tuple(
                    await session.scalars(
                        select(ConceptRow).where(
                            ConceptRow.code.in_(tuple(job.custom_ids.values()))
                        )
                    )
                )
            }
            generated = 0
            flagged = 0
            for custom_id, draft in results.items():
                concept_code = job.custom_ids.get(custom_id)
                concept = concepts.get(concept_code or "")
                if concept is None:
                    continue
                entries = [
                    (
                        draft.preferred_term,
                        "canonical" if job.target_language == "en" else "translation",
                        True,
                    ),
                    *((term, "synonym", False) for term in draft.synonyms),
                    *((term, "abbreviation", False) for term in draft.abbreviations),
                ]
                seen_normalized: set[str] = set()
                for term, kind, preferred in entries:
                    normalized = _normalize_search_text(term)
                    if not normalized or normalized in seen_normalized:
                        continue
                    seen_normalized.add(normalized)
                    flags = self._translation_qa_flags(
                        term,
                        source=concept.canonical_name_en,
                        warnings=draft.warnings,
                    )
                    row = await session.scalar(
                        select(ConceptLabelRow).where(
                            ConceptLabelRow.concept_id == concept.id,
                            ConceptLabelRow.language == job.target_language,
                            ConceptLabelRow.normalized_label == normalized,
                            ConceptLabelRow.review_status == "draft",
                        )
                    )
                    if row is None:
                        row = ConceptLabelRow(
                            concept_id=concept.id,
                            language=job.target_language,
                            normalized_label=normalized,
                        )
                        session.add(row)
                    row.label = term
                    row.definition = draft.definition if preferred else None
                    row.label_kind = kind
                    row.is_preferred = preferred
                    row.term_source = "openai"
                    row.translation_method = "openai"
                    row.translation_model = job.model
                    row.confidence = None
                    row.review_status = "draft"
                    row.prompt_version = job.prompt_version
                    row.glossary_version = job.glossary_version
                    row.tokens = normalized.split()
                    row.transliteration = MultilingualConceptResolver.fold(term)
                    row.qa_flags = flags
                    row.registry_version = concept.registry_version
                    generated += 1
                    flagged += bool(flags)
            job.status = "review_required"
            job.completed_count = len(results)
            job.failed_count = max(job.requested_count - len(results), 0)
            job.updated_at = utc_now()
            return {"draft_terms_generated": generated, "qa_flagged": flagged}

    @staticmethod
    def _translation_job_payload(row: TranslationJobRow) -> dict[str, Any]:
        return {
            "job_id": str(row.id),
            "provider": row.provider,
            "provider_job_id": row.provider_job_id,
            "input_file_id": row.input_file_id,
            "output_file_id": row.output_file_id,
            "error_file_id": row.error_file_id,
            "target_language": row.target_language,
            "model": row.model,
            "qa_model": row.qa_model,
            "prompt_version": row.prompt_version,
            "glossary_version": row.glossary_version,
            "status": row.status,
            "requested_count": row.requested_count,
            "completed_count": row.completed_count,
            "failed_count": row.failed_count,
            "custom_ids": row.custom_ids,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _translation_qa_flags(
        value: str,
        *,
        source: str,
        warnings: list[str],
    ) -> list[str]:
        normalized = _normalize_search_text(value)
        tokens = normalized.split()
        flags = list(dict.fromkeys(str(item) for item in warnings if str(item).strip()))
        if len(tokens) != len(list(dict.fromkeys(tokens))):
            flags.append("repeated_token")
        if normalized == _normalize_search_text(source):
            flags.append("unchanged_from_english")
        if len(value) > 120:
            flags.append("term_too_long")
        return list(dict.fromkeys(flags))

    @asynccontextmanager
    async def source_lock(self, source_code: str) -> Any:
        async with self._sessions() as session:
            dialect = session.bind.dialect.name if session.bind is not None else ""
            if dialect == "postgresql":
                await session.execute(
                    text("SELECT pg_advisory_lock(hashtext(:source_code))"),
                    {"source_code": source_code.upper()},
                )
            try:
                yield
            finally:
                if dialect == "postgresql":
                    await session.execute(
                        text("SELECT pg_advisory_unlock(hashtext(:source_code))"),
                        {"source_code": source_code.upper()},
                    )

    async def request_run(
        self,
        source_code: str,
        requested_by: str,
        requested_reference_year: int | None = None,
    ) -> RunRequest:
        async with self._sessions.begin() as session:
            source = await self._source_for_update(session, source_code)
            run_mode = self._validate_run_target(source, requested_reference_year)
            existing = await session.scalar(
                select(SourceRunRow).where(
                    SourceRunRow.source_id == source.id,
                    SourceRunRow.outcome == RunOutcome.RUNNING.value,
                )
            )
            if existing is not None:
                if (
                    existing.run_mode == run_mode.value
                    and existing.requested_reference_year == requested_reference_year
                ):
                    return RunRequest(run_id=existing.id, created=False)
                raise ValueError(
                    f"source already has an active {existing.run_mode} run: {source.code}"
                )

            run = SourceRunRow(
                source_id=source.id,
                requested_by=requested_by,
                run_mode=run_mode.value,
                requested_reference_year=requested_reference_year,
            )
            session.add(run)
            await session.flush()
            session.add_all(
                [
                    RunStepRow(run_id=run.id, step=step.value, status="pending")
                    for step in PIPELINE_STEPS
                ]
            )
            session.add(
                OutboxEventRow(
                    event_type="source.run.requested",
                    payload={
                        "job_id": str(uuid4()),
                        "run_id": str(run.id),
                        "source_code": source.code,
                        "attempt": 1,
                        "run_mode": run_mode.value,
                        "requested_reference_year": requested_reference_year,
                    },
                )
            )
            return RunRequest(run_id=run.id, created=True)

    async def due_source_codes(self, now: datetime) -> tuple[str, ...]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(SourceRow.code)
                .where(
                    SourceRow.status == "active",
                    SourceRow.next_check_at.is_not(None),
                    SourceRow.next_check_at <= now,
                )
                .order_by(SourceRow.next_check_at)
            )
            return tuple(rows)

    async def set_next_check(self, source_code: str, next_check_at: datetime) -> None:
        async with self._sessions.begin() as session:
            source = await self._source_for_update(session, source_code)
            source.next_check_at = next_check_at

    async def claim_outbox(self, limit: int = 50) -> tuple[OutboxMessage, ...]:
        now = utc_now()
        stale = now - timedelta(minutes=5)
        async with self._sessions.begin() as session:
            rows = list(
                await session.scalars(
                    select(OutboxEventRow)
                    .where(
                        OutboxEventRow.available_at <= now,
                        or_(
                            OutboxEventRow.status == OutboxStatus.PENDING.value,
                            and_(
                                OutboxEventRow.status == OutboxStatus.PROCESSING.value,
                                OutboxEventRow.locked_at < stale,
                            ),
                        ),
                    )
                    .order_by(OutboxEventRow.created_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            for row in rows:
                row.status = OutboxStatus.PROCESSING.value
                row.locked_at = now
                row.attempts += 1
            return tuple(
                OutboxMessage(row.id, row.event_type, row.payload, row.attempts) for row in rows
            )

    async def mark_outbox_published(self, event_id: UUID) -> None:
        async with self._sessions.begin() as session:
            row = await session.get(OutboxEventRow, event_id, with_for_update=True)
            if row is not None:
                row.status = OutboxStatus.PUBLISHED.value
                row.published_at = utc_now()
                row.locked_at = None

    async def mark_outbox_failed(self, event_id: UUID, error: str) -> None:
        async with self._sessions.begin() as session:
            row = await session.get(OutboxEventRow, event_id, with_for_update=True)
            if row is not None:
                row.status = (
                    OutboxStatus.FAILED.value if row.attempts >= 4 else OutboxStatus.PENDING.value
                )
                row.available_at = utc_now() + self.retry_delay(row.attempts)
                row.last_error = error
                row.locked_at = None

    async def enqueue_retry(self, run_id: UUID, source_code: str, attempt: int) -> None:
        delay = self.retry_delay(attempt)
        async with self._sessions.begin() as session:
            run = await session.get(SourceRunRow, run_id)
            if run is None:
                raise LookupError(run_id)
            session.add(
                OutboxEventRow(
                    event_type="source.run.requested",
                    payload={
                        "job_id": str(uuid4()),
                        "run_id": str(run_id),
                        "source_code": source_code,
                        "attempt": attempt + 1,
                        "run_mode": run.run_mode,
                        "requested_reference_year": run.requested_reference_year,
                    },
                    available_at=utc_now() + delay,
                )
            )

    async def get_run(self, run_id: UUID) -> dict[str, Any] | None:
        async with self._sessions() as session:
            run = await session.get(SourceRunRow, run_id)
            if run is None:
                return None
            source_code = await session.scalar(
                select(SourceRow.code).where(SourceRow.id == run.source_id)
            )
            steps = list(
                await session.scalars(
                    select(RunStepRow).where(RunStepRow.run_id == run_id).order_by(RunStepRow.id)
                )
            )
            return {
                "id": str(run.id),
                "source_code": source_code,
                "outcome": run.outcome,
                "requested_by": run.requested_by,
                "run_mode": run.run_mode,
                "requested_reference_year": run.requested_reference_year,
                "requested_revision": run.requested_revision,
                "attempt": run.attempt,
                "failure_retryable": run.failure_retryable,
                "error_class": run.error_class,
                "created_at": run.created_at,
                "finished_at": run.finished_at,
                "steps": [
                    {
                        "step": step.step,
                        "status": step.status,
                        "attempt": step.attempt,
                        "started_at": step.started_at,
                        "finished_at": step.finished_at,
                        "message": step.message,
                    }
                    for step in steps
                ],
            }

    async def source_history_versions(self, source_code: str) -> list[dict[str, Any]]:
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(DatasetVersionRow)
                    .join(DatasetRow, DatasetRow.id == DatasetVersionRow.dataset_id)
                    .join(SourceRow, SourceRow.id == DatasetRow.source_id)
                    .where(SourceRow.code == source_code.upper())
                    .order_by(
                        DatasetVersionRow.release_year,
                        DatasetVersionRow.retrieved_at,
                    )
                )
            ).scalars()
            return [
                {
                    "id": str(row.id),
                    "version_key": row.version_key,
                    "release_year": row.release_year,
                    # Backwards-compatible annual-source alias. The API removes this
                    # alias for YEARLY_SUBMISSION sources where it would be misleading.
                    "reference_year": row.release_year,
                    "source_published_at": row.source_published_at,
                    "retrieved_at": row.retrieved_at,
                    "workflow_status": row.status,
                    "version_status": row.version_status,
                    "checksum": row.checksum,
                    "parser_version": row.parser_version,
                    "mapping_version": row.mapping_version,
                    "metrics": row.metrics,
                }
                for row in rows
            ]

    async def run_source_code(self, run_id: UUID) -> str | None:
        async with self._sessions() as session:
            result = await session.scalar(
                select(SourceRow.code)
                .join(SourceRunRow, SourceRunRow.source_id == SourceRow.id)
                .where(SourceRunRow.id == run_id)
            )
            return str(result) if result is not None else None

    async def last_source_revision(
        self,
        source_code: str,
        *,
        reference_year: int | None = None,
        parser_version: str | None = None,
        mapping_version: str | None = None,
    ) -> str | None:
        async with self._sessions() as session:
            statement = (
                select(DatasetVersionRow.source_revision)
                .join(DatasetRow, DatasetRow.id == DatasetVersionRow.dataset_id)
                .join(SourceRow, SourceRow.id == DatasetRow.source_id)
                .where(
                    SourceRow.code == source_code,
                    DatasetVersionRow.status.in_(
                        (
                            DatasetVersionStatus.REVIEW_REQUIRED.value,
                            DatasetVersionStatus.PUBLISHED.value,
                        )
                    ),
                )
                .order_by(DatasetVersionRow.created_at.desc())
                .limit(1)
            )
            if reference_year is not None:
                statement = statement.where(DatasetVersionRow.release_year == reference_year)
            if parser_version is not None:
                statement = statement.where(DatasetVersionRow.parser_version == parser_version)
            if mapping_version is not None:
                statement = statement.where(DatasetVersionRow.mapping_version == mapping_version)
            result = await session.scalar(statement)
            return str(result) if result is not None else None

    async def save_source_check(self, context: PipelineContext) -> None:
        if context.check_result is None:
            return
        async with self._sessions.begin() as session:
            source = await session.scalar(
                select(SourceRow).where(SourceRow.code == context.source.code)
            )
            if source is None:
                raise LookupError(context.source.code)
            result = context.check_result
            source.last_checked_at = utc_now()
            session.add(
                SourceCheckRow(
                    source_id=source.id,
                    run_id=context.run.id,
                    changed=result.changed,
                    revision=result.revision,
                    etag=result.etag,
                    last_modified=result.last_modified,
                    reason=result.reason,
                )
            )

    async def record_source_check(
        self, source_code: str, run_id: UUID, result: ChangeCheckResult
    ) -> None:
        async with self._sessions.begin() as session:
            source = await session.scalar(select(SourceRow).where(SourceRow.code == source_code))
            if source is None:
                raise LookupError(source_code)
            source.last_checked_at = utc_now()
            session.add(
                SourceCheckRow(
                    source_id=source.id,
                    run_id=run_id,
                    changed=result.changed,
                    revision=result.revision,
                    etag=result.etag,
                    last_modified=result.last_modified,
                    reason=result.reason,
                )
            )

    async def record_raw_asset(
        self,
        source_code: str,
        raw: RawAssetReference,
    ) -> None:
        async with self._sessions.begin() as session:
            source = await session.scalar(
                select(SourceRow).where(SourceRow.code == source_code).with_for_update()
            )
            if source is None:
                raise LookupError(source_code)
            existing = await session.scalar(
                select(RawAssetRow.id).where(
                    RawAssetRow.source_id == source.id,
                    RawAssetRow.sha256 == raw.sha256,
                )
            )
            if existing is None:
                session.add(
                    RawAssetRow(
                        source_id=source.id,
                        bucket=raw.bucket,
                        object_key=raw.object_key,
                        sha256=raw.sha256,
                        filename=raw.filename,
                        source_url=str(raw.source_url),
                        mime_type=raw.mime_type,
                        size_bytes=raw.size_bytes,
                        downloaded_at=raw.downloaded_at,
                        metadata_json=raw.metadata,
                    )
                )

    async def persist_candidate(self, context: PipelineContext) -> str:
        if context.raw_asset is None:
            raise ValueError("raw asset is required before versioning")
        raw = context.raw_asset
        async with self._sessions.begin() as session:
            source = await session.scalar(
                select(SourceRow).where(SourceRow.code == context.source.code).with_for_update()
            )
            if source is None:
                raise LookupError(context.source.code)
            dataset = await session.scalar(
                select(DatasetRow).where(DatasetRow.source_id == source.id)
            )
            if dataset is None:
                dataset = DatasetRow(
                    source_id=source.id,
                    code=context.source.code.lower(),
                    name=context.source.name,
                )
                session.add(dataset)
                await session.flush()

            raw_row = await session.scalar(
                select(RawAssetRow).where(
                    RawAssetRow.source_id == source.id,
                    RawAssetRow.sha256 == raw.sha256,
                )
            )
            if raw_row is None:
                raw_row = RawAssetRow(
                    source_id=source.id,
                    bucket=raw.bucket,
                    object_key=raw.object_key,
                    sha256=raw.sha256,
                    filename=raw.filename,
                    source_url=str(raw.source_url),
                    mime_type=raw.mime_type,
                    size_bytes=raw.size_bytes,
                    downloaded_at=raw.downloaded_at,
                    metadata_json=raw.metadata,
                )
                session.add(raw_row)
                await session.flush()

            parser_version = context.effective_parser_version
            mapping_version = context.source.adapter.mapping_version
            existing = await session.scalar(
                select(DatasetVersionRow).where(
                    DatasetVersionRow.dataset_id == dataset.id,
                    DatasetVersionRow.checksum == raw.sha256,
                    DatasetVersionRow.parser_version == parser_version,
                    DatasetVersionRow.mapping_version == mapping_version,
                )
            )
            if existing is not None:
                if context.source_dataset_version is not None:
                    existing.version_key = (
                        f"{context.source.code.lower()}:{context.source_dataset_version}:"
                        f"{raw.sha256[:12]}"
                    )
                return str(existing.id)

            release_year = self._release_year(context)
            source_version = context.source_dataset_version or str(release_year or "unknown")
            version = DatasetVersionRow(
                dataset_id=dataset.id,
                source_run_id=context.run.id,
                raw_asset_id=raw_row.id,
                version_key=f"{context.source.code.lower()}:{source_version}:{raw.sha256[:12]}",
                release_year=release_year,
                valid_from=(date(release_year, 1, 1) if release_year is not None else None),
                valid_to=(date(release_year + 1, 1, 1) if release_year is not None else None),
                source_published_at=context.source_published_at,
                retrieved_at=raw.downloaded_at,
                source_revision=context.run.requested_revision,
                checksum=raw.sha256,
                parser_version=parser_version,
                mapping_version=mapping_version,
                status=(
                    DatasetVersionStatus.REVIEW_REQUIRED.value
                    if context.review_required
                    else DatasetVersionStatus.VALIDATED.value
                ),
                parsed_row_count=len(context.parsed_records),
                normalized_factor_count=len(context.normalized_factors),
                excluded_row_count=context.metrics.get("excluded_rows", 0),
                comparison=(
                    context.comparison_report.model_dump(mode="json")
                    if context.comparison_report
                    else {}
                ),
                metrics=context.metrics,
                version_status=TemporalVersionStatus.CANDIDATE.value,
            )
            session.add(version)
            await session.flush()

            for artifact in (context.parsed_artifact, context.normalized_artifact):
                if artifact is not None:
                    session.add(
                        ProcessingArtifactRow(
                            dataset_version_id=version.id,
                            layer=artifact.layer,
                            bucket=artifact.bucket,
                            object_key=artifact.object_key,
                            sha256=artifact.sha256,
                            row_count=artifact.row_count,
                        )
                    )

            session.add_all(
                [
                    SourceObservationRow(
                        dataset_version_id=version.id,
                        raw_asset_id=raw_row.id,
                        observation_id=observation.observation_id,
                        entity_type=observation.entity_type.value,
                        name=observation.name,
                        value=observation.value,
                        unit=observation.unit,
                        reference_year=observation.reference_year,
                        gas=observation.gas,
                        source_category=observation.source_category,
                        source_subcategory=observation.source_subcategory,
                        source_coordinates={
                            "sheet": observation.provenance.sheet,
                            "table": observation.provenance.table,
                            "row": observation.provenance.row,
                            "column_number": observation.provenance.column_number,
                            "column_name": observation.provenance.column_name,
                            "original_file": observation.provenance.original_file,
                            "file_checksum": observation.provenance.file_checksum,
                            "parser_version": observation.provenance.parser_version,
                            "mapping_version": observation.provenance.mapping_version,
                        },
                        attributes=observation.attributes,
                    )
                    for observation in context.source_observations
                ]
            )

            logical_ids = list(
                dict.fromkeys(factor.logical_factor_id for factor in context.normalized_factors)
            )
            existing_logicals: list[FactorRow] = []
            for offset in range(0, len(logical_ids), 5_000):
                batch = logical_ids[offset : offset + 5_000]
                existing_logicals.extend(
                    await session.scalars(select(FactorRow).where(FactorRow.logical_id.in_(batch)))
                )
            logical_by_id = {row.logical_id: row for row in existing_logicals}
            new_logicals: list[FactorRow] = []
            for factor in context.normalized_factors:
                if factor.logical_factor_id not in logical_by_id:
                    logical = FactorRow(
                        id=uuid4(),
                        source_id=source.id,
                        logical_id=factor.logical_factor_id,
                    )
                    logical_by_id[factor.logical_factor_id] = logical
                    new_logicals.append(logical)
            session.add_all(new_logicals)

            factor_versions: list[FactorVersionRow] = []
            sector_assignments: list[FactorSectorAssignmentRow] = []
            provenance_rows: list[ProvenanceRow] = []
            await self._ensure_sector_registry(session)
            for factor in context.normalized_factors:
                logical = logical_by_id[factor.logical_factor_id]
                factor_version_id = uuid4()
                factor_valid_from = factor.valid_from
                factor_valid_to = factor.valid_to
                if factor.reference_year is not None:
                    factor_valid_from = factor_valid_from or date(factor.reference_year, 1, 1)
                    factor_valid_to = factor_valid_to or date(factor.reference_year + 1, 1, 1)
                factor_version = FactorVersionRow(
                    id=factor_version_id,
                    factor_id=logical.id,
                    dataset_version_id=version.id,
                    source_factor_id=factor.source_factor_id or factor.logical_factor_id,
                    name=factor.name,
                    description=factor.description,
                    taxonomy_code=factor.taxonomy_code or "atlas.unmapped",
                    activity_type=factor.activity_type,
                    activity_unit=factor.activity_unit,
                    factor_value=factor.factor_value,
                    factor_unit=factor.factor_unit,
                    entity_type=factor.entity_type.value,
                    factor_value_kind=factor.factor_value_kind.value,
                    intended_use=factor.intended_use.value,
                    gases=factor.gases.model_dump(mode="json"),
                    origin_geography=(
                        factor.origin_geography.model_dump(mode="json")
                        if factor.origin_geography
                        else None
                    ),
                    applicable_geographies=[
                        geography.model_dump(mode="json")
                        for geography in factor.applicable_geographies
                    ],
                    geography_roles=[
                        assignment.model_dump(mode="json") for assignment in factor.geography_roles
                    ],
                    geography_level=factor.geography_level.value,
                    geographic_specificity=factor.geographic_specificity,
                    geographic_fit_type=factor.geographic_fit_type.value,
                    reference_year=factor.reference_year,
                    valid_from=factor_valid_from,
                    valid_to=factor_valid_to,
                    source_published_at=context.source_published_at,
                    retrieved_at=raw.downloaded_at,
                    version_status=TemporalVersionStatus.CANDIDATE.value,
                    methodology=factor.methodology.model_dump(mode="json"),
                    data_quality=factor.data_quality,
                    source_payload={
                        "source_category": factor.source_category,
                        "source_subcategory": factor.source_subcategory,
                    },
                )
                factor_versions.append(factor_version)
                sector = self._sector_policy.classify(factor.taxonomy_code)
                sector_assignments.append(
                    FactorSectorAssignmentRow(
                        factor_version_id=factor_version_id,
                        sector_code=sector.sector_code,
                        category_code=sector.category_code,
                        is_primary=True,
                        derivation="verified_crosswalk",
                        confidence=sector.confidence,
                        evidence={
                            "taxonomy_code": factor.taxonomy_code or "atlas.unmapped",
                            "source_category": factor.source_category,
                            "rule": sector.rule_code,
                        },
                        mapping_version=sector.mapping_version,
                        review_status="approved",
                    )
                )
                for provenance in (factor.provenance, *factor.component_provenance):
                    provenance_rows.append(
                        ProvenanceRow(
                            factor_version_id=factor_version_id,
                            raw_asset_id=raw_row.id,
                            role=provenance.role.value,
                            sheet=provenance.sheet,
                            table_name=provenance.table,
                            row_number=provenance.row,
                            column_number=provenance.column_number,
                            column_name=provenance.column_name,
                            original_factor_name=provenance.original_factor_name,
                            original_unit=provenance.original_unit,
                            parser_version=provenance.parser_version,
                            mapping_version=provenance.mapping_version,
                        )
                    )
            session.add_all(factor_versions)
            session.add_all(sector_assignments)
            session.add_all(provenance_rows)

            if context.quality_report is not None:
                session.add_all(
                    [
                        QualityResultRow(
                            dataset_version_id=version.id,
                            rule_code=finding.rule_code,
                            severity=finding.severity.value,
                            message=finding.message,
                            factor_logical_id=finding.factor_id,
                            details=finding.details,
                        )
                        for finding in context.quality_report.findings
                    ]
                )

            if context.review_required:
                reasons = list(
                    context.comparison_report.review_reasons
                    if context.comparison_report is not None
                    else ()
                )
                if context.quality_report is not None:
                    reasons.extend(
                        finding.rule_code
                        for finding in context.quality_report.findings
                        if finding.severity.value in {"fail", "review_required"}
                    )
                session.add(
                    ReviewRow(
                        dataset_version_id=version.id,
                        reasons=sorted(set(reasons)) or ["manual_review_required"],
                    )
                )
            return str(version.id)

    async def has_published_dataset(self, source_code: str) -> bool:
        async with self._sessions() as session:
            result = await session.scalar(
                select(DatasetVersionRow.id)
                .join(DatasetRow, DatasetRow.id == DatasetVersionRow.dataset_id)
                .join(SourceRow, SourceRow.id == DatasetRow.source_id)
                .where(
                    SourceRow.code == source_code,
                    DatasetVersionRow.status == DatasetVersionStatus.PUBLISHED.value,
                )
                .limit(1)
            )
            return result is not None

    async def published_factor_values(
        self, source_code: str, *, reference_year: int | None = None
    ) -> dict[str, Any]:
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(FactorVersionRow.source_factor_id, FactorVersionRow.factor_value)
                    .join(
                        DatasetVersionRow,
                        DatasetVersionRow.id == FactorVersionRow.dataset_version_id,
                    )
                    .join(DatasetRow, DatasetRow.id == DatasetVersionRow.dataset_id)
                    .join(SourceRow, SourceRow.id == DatasetRow.source_id)
                    .where(
                        SourceRow.code == source_code,
                        DatasetVersionRow.status == DatasetVersionStatus.PUBLISHED.value,
                        FactorVersionRow.version_status == TemporalVersionStatus.CURRENT.value,
                    )
                    .order_by(
                        FactorVersionRow.reference_year.desc().nullslast(),
                        FactorVersionRow.system_effective_from.desc().nullslast(),
                    )
                )
            ).all()
            if reference_year is not None:
                rows = (
                    await session.execute(
                        select(
                            FactorVersionRow.source_factor_id,
                            FactorVersionRow.factor_value,
                        )
                        .join(
                            DatasetVersionRow,
                            DatasetVersionRow.id == FactorVersionRow.dataset_version_id,
                        )
                        .join(DatasetRow, DatasetRow.id == DatasetVersionRow.dataset_id)
                        .join(SourceRow, SourceRow.id == DatasetRow.source_id)
                        .where(
                            SourceRow.code == source_code,
                            DatasetVersionRow.status == DatasetVersionStatus.PUBLISHED.value,
                            FactorVersionRow.version_status == TemporalVersionStatus.CURRENT.value,
                            FactorVersionRow.reference_year == reference_year,
                        )
                    )
                ).all()
            values: dict[str, Any] = {}
            for source_factor_id, factor_value in rows:
                values.setdefault(source_factor_id, factor_value)
            return values

    async def publish_version(self, dataset_version_id: UUID) -> None:
        async with self._sessions.begin() as session:
            version = await session.get(DatasetVersionRow, dataset_version_id, with_for_update=True)
            if version is None:
                raise LookupError(str(dataset_version_id))
            if version.status == DatasetVersionStatus.REVIEW_REQUIRED.value:
                raise ValueError("review-required dataset cannot be published automatically")
            dataset = await session.get(DatasetRow, version.dataset_id, with_for_update=True)
            if dataset is None:
                raise LookupError(str(version.dataset_id))
            source = await session.get(SourceRow, dataset.source_id, with_for_update=True)
            await self._activate_version(session, version, dataset, source)

    async def approve_review(self, review_id: UUID, decided_by: str, note: str | None) -> None:
        async with self._sessions.begin() as session:
            review = await session.get(ReviewRow, review_id, with_for_update=True)
            if review is None:
                raise LookupError(str(review_id))
            if review.status != ReviewStatus.PENDING.value:
                raise ValueError("review is already decided")
            version = await session.get(
                DatasetVersionRow, review.dataset_version_id, with_for_update=True
            )
            if version is None:
                raise LookupError(str(review.dataset_version_id))
            dataset = await session.get(DatasetRow, version.dataset_id, with_for_update=True)
            if dataset is None:
                raise LookupError(str(version.dataset_id))
            source = await session.get(SourceRow, dataset.source_id, with_for_update=True)
            review.status = ReviewStatus.APPROVED.value
            review.decided_at = utc_now()
            review.decided_by = decided_by
            review.decision_note = note
            await self._activate_version(session, version, dataset, source)

    async def reject_review(self, review_id: UUID, decided_by: str, note: str | None) -> None:
        async with self._sessions.begin() as session:
            review = await session.get(ReviewRow, review_id, with_for_update=True)
            if review is None:
                raise LookupError(str(review_id))
            if review.status != ReviewStatus.PENDING.value:
                raise ValueError("review is already decided")
            version = await session.get(
                DatasetVersionRow, review.dataset_version_id, with_for_update=True
            )
            if version is None:
                raise LookupError(str(review.dataset_version_id))
            review.status = ReviewStatus.REJECTED.value
            review.decided_at = utc_now()
            review.decided_by = decided_by
            review.decision_note = note
            version.status = DatasetVersionStatus.REJECTED.value
            version.version_status = TemporalVersionStatus.REJECTED.value
            factor_versions = list(
                await session.scalars(
                    select(FactorVersionRow).where(
                        FactorVersionRow.dataset_version_id == version.id
                    )
                )
            )
            for factor_version in factor_versions:
                factor_version.version_status = TemporalVersionStatus.REJECTED.value

    async def list_reviews(self, status: str = "pending") -> list[dict[str, Any]]:
        async with self._sessions() as session:
            rows = list(
                await session.scalars(
                    select(ReviewRow)
                    .where(ReviewRow.status == status)
                    .order_by(ReviewRow.requested_at)
                )
            )
            return [
                {
                    "id": str(row.id),
                    "dataset_version_id": str(row.dataset_version_id),
                    "status": row.status,
                    "reasons": row.reasons,
                    "requested_at": row.requested_at,
                    "decided_at": row.decided_at,
                    "decided_by": row.decided_by,
                }
                for row in rows
            ]

    async def list_datasets(self) -> list[dict[str, Any]]:
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(DatasetRow, DatasetVersionRow, SourceRow)
                    .join(
                        DatasetVersionRow,
                        DatasetVersionRow.id == DatasetRow.current_version_id,
                    )
                    .join(SourceRow, SourceRow.id == DatasetRow.source_id)
                    .order_by(SourceRow.code)
                )
            ).all()
            return [
                {
                    "id": str(dataset.id),
                    "code": dataset.code,
                    "name": dataset.name,
                    "source_code": source.code,
                    "current_version_id": str(version.id),
                    "version_key": version.version_key,
                    "release_year": version.release_year,
                    "valid_from": version.valid_from,
                    "valid_to": version.valid_to,
                    "source_published_at": version.source_published_at,
                    "retrieved_at": version.retrieved_at,
                    "effective_from": version.system_effective_from,
                    "effective_to": version.system_effective_to,
                    "version_status": version.version_status,
                    "factor_count": version.normalized_factor_count,
                    "observation_count": version.metrics.get("source_observations", 0),
                    "metrics": version.metrics,
                    "published_at": version.published_at,
                }
                for dataset, version, source in rows
            ]

    async def get_dataset(self, dataset_id: UUID) -> dict[str, Any] | None:
        async with self._sessions() as session:
            row = (
                await session.execute(
                    select(DatasetRow, DatasetVersionRow, SourceRow)
                    .join(
                        DatasetVersionRow,
                        DatasetVersionRow.id == DatasetRow.current_version_id,
                    )
                    .join(SourceRow, SourceRow.id == DatasetRow.source_id)
                    .where(DatasetRow.id == dataset_id)
                )
            ).one_or_none()
            if row is None:
                return None
            dataset, version, source = row
            return {
                "id": str(dataset.id),
                "code": dataset.code,
                "name": dataset.name,
                "source_code": source.code,
                "current_version": {
                    "id": str(version.id),
                    "version_key": version.version_key,
                    "release_year": version.release_year,
                    "valid_from": version.valid_from,
                    "valid_to": version.valid_to,
                    "source_published_at": version.source_published_at,
                    "retrieved_at": version.retrieved_at,
                    "effective_from": version.system_effective_from,
                    "effective_to": version.system_effective_to,
                    "version_status": version.version_status,
                    "parser_version": version.parser_version,
                    "mapping_version": version.mapping_version,
                    "factor_count": version.normalized_factor_count,
                    "observation_count": version.metrics.get("source_observations", 0),
                    "metrics": version.metrics,
                    "published_at": version.published_at,
                },
            }

    async def dataset_versions(self, dataset_id: UUID) -> list[dict[str, Any]]:
        async with self._sessions() as session:
            versions = list(
                await session.scalars(
                    select(DatasetVersionRow)
                    .where(DatasetVersionRow.dataset_id == dataset_id)
                    .order_by(
                        DatasetVersionRow.release_year,
                        DatasetVersionRow.system_effective_from,
                        DatasetVersionRow.created_at,
                    )
                )
            )
            return [
                {
                    "id": str(version.id),
                    "version_key": version.version_key,
                    "release_year": version.release_year,
                    "valid_from": version.valid_from,
                    "valid_to": version.valid_to,
                    "source_published_at": version.source_published_at,
                    "retrieved_at": version.retrieved_at,
                    "effective_from": version.system_effective_from,
                    "effective_to": version.system_effective_to,
                    "superseded_at": version.superseded_at,
                    "supersedes_version_id": (
                        str(version.supersedes_version_id)
                        if version.supersedes_version_id is not None
                        else None
                    ),
                    "version_status": version.version_status,
                    "workflow_status": version.status,
                    "parser_version": version.parser_version,
                    "mapping_version": version.mapping_version,
                    "factor_count": version.normalized_factor_count,
                    "observation_count": version.metrics.get("source_observations", 0),
                    "metrics": version.metrics,
                }
                for version in versions
            ]

    async def list_published_factors(
        self,
        *,
        limit: int,
        cursor: str | None = None,
        query: str | None = None,
        concept_codes: tuple[str, ...] = (),
        source_code: str | None = None,
        taxonomy_code: str | None = None,
        geography_code: str | None = None,
        geography_codes: tuple[str, ...] = (),
        origin_geography_code: str | None = None,
        reference_year: int | None = None,
        entity_type: str | None = None,
        entity_types: tuple[str, ...] = (),
        factor_value_kind: str | None = None,
        intended_use: str | None = None,
        scope: str | None = None,
        sector_code: str | None = None,
        category_code: str | None = None,
        known_at: datetime | None = None,
    ) -> list[dict[str, Any]]:
        async with self._sessions() as session:
            statement = (
                select(
                    FactorRow,
                    FactorVersionRow,
                    SourceRow,
                    FactorSectorAssignmentRow,
                )
                .join(FactorVersionRow, FactorVersionRow.factor_id == FactorRow.id)
                .join(
                    DatasetVersionRow,
                    DatasetVersionRow.id == FactorVersionRow.dataset_version_id,
                )
                .join(SourceRow, SourceRow.id == FactorRow.source_id)
                .outerjoin(
                    FactorSectorAssignmentRow,
                    FactorSectorAssignmentRow.factor_version_id == FactorVersionRow.id,
                )
                .where(DatasetVersionRow.status == DatasetVersionStatus.PUBLISHED.value)
                .order_by(
                    FactorRow.logical_id,
                    func.coalesce(FactorVersionRow.reference_year, -1),
                    FactorVersionRow.id,
                )
                .limit(limit)
            )
            if known_at is None:
                statement = statement.where(
                    FactorVersionRow.version_status == TemporalVersionStatus.CURRENT.value
                )
            else:
                statement = statement.where(
                    FactorVersionRow.system_effective_from <= known_at,
                    or_(
                        FactorVersionRow.system_effective_to.is_(None),
                        FactorVersionRow.system_effective_to > known_at,
                    ),
                )
            if cursor:
                try:
                    cursor_logical, cursor_year, cursor_version = cursor.rsplit("|", 2)
                    cursor_year_value = int(cursor_year) if cursor_year else -1
                    cursor_version_id = UUID(cursor_version)
                except (ValueError, TypeError) as error:
                    raise ValueError("invalid factor cursor") from error
                year_expression = func.coalesce(FactorVersionRow.reference_year, -1)
                statement = statement.where(
                    or_(
                        FactorRow.logical_id > cursor_logical,
                        and_(
                            FactorRow.logical_id == cursor_logical,
                            year_expression > cursor_year_value,
                        ),
                        and_(
                            FactorRow.logical_id == cursor_logical,
                            year_expression == cursor_year_value,
                            FactorVersionRow.id > cursor_version_id,
                        ),
                    )
                )
            if source_code:
                statement = statement.where(SourceRow.code == source_code.upper())
            text_search = None
            if query:
                searchable_columns = (
                    FactorVersionRow.name,
                    FactorRow.logical_id,
                    FactorVersionRow.source_factor_id,
                    FactorVersionRow.taxonomy_code,
                    FactorVersionRow.activity_type,
                    FactorVersionRow.factor_unit,
                    cast(FactorVersionRow.applicable_geographies, Text),
                    cast(FactorVersionRow.geography_roles, Text),
                )
                token_clauses = []
                for token in _normalize_search_text(query).split():
                    token_clauses.append(
                        or_(*(column.ilike(f"%{token}%") for column in searchable_columns))
                    )
                if token_clauses:
                    text_search = and_(*token_clauses)
            concept_search = None
            if concept_codes:
                concept_search = (
                    select(1)
                    .select_from(FactorConceptRow)
                    .join(ConceptRow, ConceptRow.id == FactorConceptRow.concept_id)
                    .where(
                        FactorConceptRow.factor_id == FactorRow.id,
                        FactorConceptRow.review_status == "approved",
                        ConceptRow.active.is_(True),
                        ConceptRow.code.in_(concept_codes),
                    )
                    .exists()
                )
            if text_search is not None and concept_search is not None:
                statement = statement.where(or_(text_search, concept_search))
            elif text_search is not None:
                statement = statement.where(text_search)
            elif concept_search is not None:
                statement = statement.where(concept_search)
            if taxonomy_code:
                statement = statement.where(FactorVersionRow.taxonomy_code == taxonomy_code)
            if geography_code:
                statement = statement.where(
                    type_coerce(FactorVersionRow.applicable_geographies, JSONB).contains(
                        [{"code": geography_code}]
                    )
                )
            if geography_codes:
                statement = statement.where(
                    or_(
                        *(
                            type_coerce(FactorVersionRow.applicable_geographies, JSONB).contains(
                                [{"code": code}]
                            )
                            for code in geography_codes
                        )
                    )
                )
            if origin_geography_code:
                statement = statement.where(
                    FactorVersionRow.origin_geography["code"].as_string() == origin_geography_code
                )
            if reference_year is not None:
                statement = statement.where(FactorVersionRow.reference_year == reference_year)
            if entity_type:
                statement = statement.where(FactorVersionRow.entity_type == entity_type)
            elif entity_types:
                statement = statement.where(FactorVersionRow.entity_type.in_(entity_types))
            if factor_value_kind:
                statement = statement.where(FactorVersionRow.factor_value_kind == factor_value_kind)
            if intended_use:
                statement = statement.where(FactorVersionRow.intended_use == intended_use)
            if scope:
                scope_expression = func.lower(
                    func.coalesce(FactorVersionRow.methodology["scope"].as_string(), "")
                )
                boundary_expression = func.lower(
                    func.coalesce(
                        FactorVersionRow.methodology["system_boundary"].as_string(),
                        "",
                    )
                )
                if scope == "unspecified":
                    statement = statement.where(
                        scope_expression == "",
                        boundary_expression != "national_inventory_implied_factor",
                    )
                else:
                    scope_number = scope.rsplit("_", 1)[-1]
                    declared_scope = scope_expression.like(f"%scope%{scope_number}%")
                    if scope == "scope_1":
                        statement = statement.where(
                            or_(
                                declared_scope,
                                boundary_expression == "national_inventory_implied_factor",
                            )
                        )
                    else:
                        statement = statement.where(declared_scope)
            if sector_code:
                statement = statement.where(FactorSectorAssignmentRow.sector_code == sector_code)
            if category_code:
                statement = statement.where(
                    FactorSectorAssignmentRow.category_code == category_code
                )
            rows = (await session.execute(statement)).all()
            return [
                self._factor_payload(logical, version, source, sector)
                for logical, version, source, sector in rows
            ]

    async def coverage_candidates(self, *, source_code: str | None = None) -> list[dict[str, Any]]:
        async with self._sessions() as session:
            statement = (
                select(
                    FactorRow,
                    FactorVersionRow,
                    SourceRow,
                    FactorSectorAssignmentRow,
                )
                .join(FactorVersionRow, FactorVersionRow.factor_id == FactorRow.id)
                .join(
                    DatasetVersionRow,
                    DatasetVersionRow.id == FactorVersionRow.dataset_version_id,
                )
                .join(SourceRow, SourceRow.id == FactorRow.source_id)
                .outerjoin(
                    FactorSectorAssignmentRow,
                    FactorSectorAssignmentRow.factor_version_id == FactorVersionRow.id,
                )
                .where(
                    DatasetVersionRow.status == DatasetVersionStatus.PUBLISHED.value,
                    FactorVersionRow.version_status == TemporalVersionStatus.CURRENT.value,
                    FactorVersionRow.entity_type.in_(
                        ("emission_factor", "implied_emission_factor")
                    ),
                    FactorVersionRow.factor_value_kind == "co2e_total",
                    FactorVersionRow.intended_use == "inventory",
                )
                .order_by(FactorRow.logical_id, DatasetVersionRow.published_at.desc())
            )
            if source_code:
                statement = statement.where(SourceRow.code == source_code.upper())
            rows = (await session.execute(statement)).all()
            latest: dict[str, dict[str, Any]] = {}
            for logical, version, source, sector in rows:
                latest.setdefault(
                    logical.logical_id,
                    self._factor_payload(logical, version, source, sector),
                )
            return list(latest.values())

    async def matching_candidates(
        self,
        *,
        activity: str,
        geography_codes: tuple[str, ...],
        activity_terms: tuple[str, ...] = (),
        include_geographic_proxies: bool = False,
        entity_types: tuple[str, ...] = ("emission_factor", "implied_emission_factor"),
        factor_value_kinds: tuple[str, ...] = ("co2e_total",),
        intended_uses: tuple[str, ...] = ("inventory",),
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        normalized_terms = tuple(
            dict.fromkeys(
                item.strip().replace("_", " ")
                for item in (activity, *activity_terms)
                if item.strip()
            )
        )
        text_clauses = tuple(
            clause
            for term in normalized_terms
            for clause in (
                FactorVersionRow.taxonomy_code.ilike(f"%{term}%"),
                FactorVersionRow.activity_type.ilike(f"%{term}%"),
                FactorVersionRow.name.ilike(f"%{term}%"),
            )
        )
        async with self._sessions() as session:
            geography_clauses = tuple(
                type_coerce(FactorVersionRow.applicable_geographies, JSONB).contains(
                    [{"code": code}]
                )
                for code in geography_codes
            )
            statement = (
                select(
                    FactorRow,
                    FactorVersionRow,
                    SourceRow,
                    FactorSectorAssignmentRow,
                )
                .join(FactorVersionRow, FactorVersionRow.factor_id == FactorRow.id)
                .join(
                    DatasetVersionRow,
                    DatasetVersionRow.id == FactorVersionRow.dataset_version_id,
                )
                .join(SourceRow, SourceRow.id == FactorRow.source_id)
                .outerjoin(
                    FactorSectorAssignmentRow,
                    FactorSectorAssignmentRow.factor_version_id == FactorVersionRow.id,
                )
                .where(
                    DatasetVersionRow.status == DatasetVersionStatus.PUBLISHED.value,
                    FactorVersionRow.version_status == TemporalVersionStatus.CURRENT.value,
                    FactorVersionRow.entity_type.in_(entity_types),
                    FactorVersionRow.factor_value_kind.in_(factor_value_kinds),
                    FactorVersionRow.intended_use.in_(intended_uses),
                    or_(*text_clauses),
                )
                .order_by(FactorRow.logical_id, DatasetVersionRow.published_at.desc())
                .limit(limit)
            )
            if geography_clauses and not include_geographic_proxies:
                statement = statement.where(or_(*geography_clauses))
            rows = (await session.execute(statement)).all()
            latest: dict[str, dict[str, Any]] = {}
            for logical, version, source, sector in rows:
                latest.setdefault(
                    logical.logical_id,
                    self._factor_payload(logical, version, source, sector),
                )
            return list(latest.values())

    async def recommendation_candidates(
        self,
        *,
        query: str,
        family_code: str,
        policy_version: str,
        classification_prefixes: tuple[str, ...] = (),
        geography_codes: tuple[str, ...],
        reference_year: int | None = None,
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        """Read the serving projection directly instead of scanning the catalog index."""

        async with self._sessions() as session:
            statement = (
                select(
                    FactorRow,
                    FactorVersionRow,
                    SourceRow,
                    FactorApplicabilityRow,
                    FactorSectorAssignmentRow,
                )
                .join(FactorVersionRow, FactorVersionRow.factor_id == FactorRow.id)
                .join(
                    DatasetVersionRow,
                    DatasetVersionRow.id == FactorVersionRow.dataset_version_id,
                )
                .join(SourceRow, SourceRow.id == FactorRow.source_id)
                .join(
                    FactorApplicabilityRow,
                    FactorApplicabilityRow.factor_version_id == FactorVersionRow.id,
                )
                .outerjoin(
                    FactorSectorAssignmentRow,
                    FactorSectorAssignmentRow.factor_version_id == FactorVersionRow.id,
                )
                .where(
                    DatasetVersionRow.status == DatasetVersionStatus.PUBLISHED.value,
                    FactorVersionRow.version_status == TemporalVersionStatus.CURRENT.value,
                    FactorApplicabilityRow.family_code == family_code,
                    FactorApplicabilityRow.policy_version == policy_version,
                )
                .order_by(
                    FactorVersionRow.geographic_specificity.desc(),
                    FactorVersionRow.reference_year.desc().nullslast(),
                    FactorRow.logical_id,
                )
                .limit(limit)
            )
            if geography_codes:
                geography_clauses = tuple(
                    type_coerce(FactorVersionRow.applicable_geographies, JSONB).contains(
                        [{"code": code}]
                    )
                    for code in geography_codes
                )
                statement = statement.where(or_(*geography_clauses))
            if family_code in {
                "air_travel",
                "purchased_services",
                "refrigerants",
                "waste",
            }:
                if classification_prefixes:
                    statement = statement.where(
                        or_(
                            *(
                                FactorVersionRow.taxonomy_code.ilike(f"{prefix}%")
                                for prefix in classification_prefixes
                            )
                        )
                    )
                else:
                    tokens = tuple(
                        token for token in _normalize_search_text(query).split() if len(token) >= 3
                    )
                    lexical_clauses = [
                        FactorVersionRow.name.ilike(f"%{token}%") for token in tokens
                    ]
                    if lexical_clauses:
                        statement = statement.where(or_(*lexical_clauses))
            rows = (await session.execute(statement)).all()
        closest: dict[str, tuple[tuple[int, int, int, int, int], dict[str, Any]]] = {}
        for rank, (logical, version, source, applicability, sector) in enumerate(rows):
            payload = self._factor_payload(logical, version, source, sector)
            payload["applicability"] = self._applicability_payload(applicability)
            temporal_key = _reference_year_preference(
                reference_year,
                version.reference_year,
                rank,
            )
            current = closest.get(logical.logical_id)
            if current is None or temporal_key < current[0]:
                closest[logical.logical_id] = (temporal_key, payload)
        return [item[1] for item in closest.values()]

    async def rebuild_recommendation_projection(
        self,
        policy: RecommendationPolicy,
        *,
        profiles: tuple[str, ...],
    ) -> dict[str, Any]:
        """Rebuild serving metadata only; published source facts are never rewritten."""

        counts: dict[str, int] = {}
        projected = 0
        async with self._sessions.begin() as session:
            await session.execute(delete(FactorApplicabilityRow))
            await session.execute(delete(FallbackPolicyRow))
            policy_rows: list[dict[str, Any]] = []
            countries = ("*", *sorted(policy.jurisdictions))
            for profile in profiles:
                for country in countries:
                    for family_code in policy.families:
                        for tier in policy.fallback_tiers:
                            policy_rows.append(
                                {
                                    "id": uuid4(),
                                    "country_code": country,
                                    "calculation_profile": profile,
                                    "family_code": family_code,
                                    "tier_code": str(tier["code"]),
                                    "tier_rank": int(tier["rank"]),
                                    "proxy": bool(tier["proxy"]),
                                    "requires_acceptance": bool(tier["proxy"]),
                                    "policy_version": policy.version,
                                }
                            )
            if policy_rows:
                await session.execute(insert(FallbackPolicyRow), policy_rows)

            statement = (
                select(FactorRow, FactorVersionRow, SourceRow)
                .join(FactorVersionRow, FactorVersionRow.factor_id == FactorRow.id)
                .join(
                    DatasetVersionRow,
                    DatasetVersionRow.id == FactorVersionRow.dataset_version_id,
                )
                .join(SourceRow, SourceRow.id == FactorRow.source_id)
                .where(
                    DatasetVersionRow.status == DatasetVersionStatus.PUBLISHED.value,
                    FactorVersionRow.version_status == TemporalVersionStatus.CURRENT.value,
                )
                .execution_options(yield_per=2000)
            )
            stream = await session.stream(statement)
            batch: list[dict[str, Any]] = []
            async for logical, version, source in stream:
                factor = self._factor_payload(logical, version, source)
                applicability = policy.classify_factor(factor)
                if applicability is None:
                    continue
                batch.append(
                    {
                        "factor_version_id": version.id,
                        **applicability,
                    }
                )
                family = str(applicability["family_code"])
                counts[family] = counts.get(family, 0) + 1
                projected += 1
                if len(batch) >= 2000:
                    await session.execute(insert(FactorApplicabilityRow), batch)
                    batch.clear()
            if batch:
                await session.execute(insert(FactorApplicabilityRow), batch)
        return {
            "policy_version": policy.version,
            "projected": projected,
            "families": counts,
            "fallback_policy_rows": len(policy_rows),
        }

    async def recommendation_projection_coverage(
        self, policy: RecommendationPolicy
    ) -> dict[str, Any]:
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(
                        FactorApplicabilityRow.family_code,
                        func.count(FactorApplicabilityRow.factor_version_id),
                    )
                    .where(FactorApplicabilityRow.policy_version == policy.version)
                    .group_by(FactorApplicabilityRow.family_code)
                )
            ).all()
            policy_count = await session.scalar(
                select(func.count(FallbackPolicyRow.id)).where(
                    FallbackPolicyRow.policy_version == policy.version
                )
            )
            category_rows = (
                await session.execute(
                    select(
                        FactorApplicabilityRow.family_code,
                        FactorApplicabilityRow.scope3_categories,
                        func.count(FactorApplicabilityRow.factor_version_id),
                    )
                    .where(
                        FactorApplicabilityRow.policy_version == policy.version,
                        FactorApplicabilityRow.scope_category == "scope_3",
                    )
                    .group_by(
                        FactorApplicabilityRow.family_code,
                        FactorApplicabilityRow.scope3_categories,
                    )
                )
            ).all()
        counts = {str(family): int(count) for family, count in rows}
        missing = sorted(set(policy.families) - set(counts))
        scope3_category_mismatches = sum(
            int(count)
            for family, categories, count in category_rows
            if tuple(int(code) for code in (categories or ()))
            != policy.scope3_categories_for_family(str(family))
        )
        return {
            "ready": not missing and bool(policy_count) and scope3_category_mismatches == 0,
            "policy_version": policy.version,
            "families": counts,
            "missing_families": missing,
            "scope3_category_mismatches": scope3_category_mismatches,
            "fallback_policy_rows": int(policy_count or 0),
        }

    async def rebuild_sector_projection(self) -> dict[str, Any]:
        """Rebuild derived sector assignments without changing source-faithful records."""

        counts: dict[str, int] = {}
        fallback_count = 0
        projected = 0
        async with self._sessions.begin() as session:
            await self._ensure_sector_registry(session)
            await session.execute(delete(FactorSectorAssignmentRow))
            stream = await session.stream(
                select(FactorVersionRow.id, FactorVersionRow.taxonomy_code)
                .order_by(FactorVersionRow.id)
                .execution_options(yield_per=5000)
            )
            batch: list[dict[str, Any]] = []
            async for factor_version_id, taxonomy_code in stream:
                assignment = self._sector_policy.classify(taxonomy_code)
                batch.append(
                    {
                        "factor_version_id": factor_version_id,
                        "sector_code": assignment.sector_code,
                        "category_code": assignment.category_code,
                        "is_primary": True,
                        "derivation": "verified_crosswalk",
                        "confidence": assignment.confidence,
                        "evidence": {
                            "taxonomy_code": taxonomy_code,
                            "rule": assignment.rule_code,
                        },
                        "mapping_version": assignment.mapping_version,
                        "review_status": "approved",
                    }
                )
                projected += 1
                counts[assignment.sector_code] = counts.get(assignment.sector_code, 0) + 1
                if assignment.confidence < 100:
                    fallback_count += 1
                if len(batch) >= 5000:
                    await session.execute(insert(FactorSectorAssignmentRow), batch)
                    batch.clear()
            if batch:
                await session.execute(insert(FactorSectorAssignmentRow), batch)
        return {
            "registry_version": self._sector_policy.version,
            "projected": projected,
            "explicit_fallbacks": fallback_count,
            "sectors": counts,
        }

    async def sector_projection_coverage(self) -> dict[str, Any]:
        async with self._sessions() as session:
            factor_total = int(await session.scalar(select(func.count(FactorVersionRow.id))) or 0)
            projected_total = int(
                await session.scalar(
                    select(func.count(FactorSectorAssignmentRow.factor_version_id))
                )
                or 0
            )
            stale_total = int(
                await session.scalar(
                    select(func.count(FactorSectorAssignmentRow.factor_version_id)).where(
                        FactorSectorAssignmentRow.mapping_version != self._sector_policy.version
                    )
                )
                or 0
            )
            fallback_total = int(
                await session.scalar(
                    select(func.count(FactorSectorAssignmentRow.factor_version_id)).where(
                        FactorSectorAssignmentRow.confidence < 100
                    )
                )
                or 0
            )
            sector_rows = (
                await session.execute(
                    select(
                        FactorSectorAssignmentRow.sector_code,
                        func.count(FactorSectorAssignmentRow.factor_version_id),
                    ).group_by(FactorSectorAssignmentRow.sector_code)
                )
            ).all()
        return {
            "ready": factor_total == projected_total and stale_total == 0,
            "registry_version": self._sector_policy.version,
            "factor_versions": factor_total,
            "projected": projected_total,
            "missing": max(factor_total - projected_total, 0),
            "stale": stale_total,
            "explicit_fallbacks": fallback_total,
            "sectors": {str(code): int(count) for code, count in sector_rows},
        }

    @staticmethod
    def _applicability_payload(row: FactorApplicabilityRow) -> dict[str, Any]:
        return {
            "concept_code": row.concept_code,
            "family_code": row.family_code,
            "calculation_role": row.calculation_role,
            "calculation_method": row.calculation_method,
            "scope_category": row.scope_category,
            "scope3_categories": row.scope3_categories,
            "activity_basis": row.activity_basis,
            "boundary": row.boundary,
            "fallback_class": row.fallback_class,
            "qualifiers": row.qualifiers,
            "policy_version": row.policy_version,
            "review_status": row.review_status,
        }

    @staticmethod
    def _sector_assignment_payload(row: FactorSectorAssignmentRow) -> dict[str, Any]:
        return {
            "sector_code": row.sector_code,
            "category_code": row.category_code,
            "primary": row.is_primary,
            "derivation": row.derivation,
            "confidence": row.confidence,
            "evidence": row.evidence,
            "mapping_version": row.mapping_version,
            "review_status": row.review_status,
        }

    async def search_candidates(
        self,
        *,
        query: str,
        concept_codes: tuple[str, ...] = (),
        geography_codes: tuple[str, ...] = (),
        entity_types: tuple[str, ...] = (),
        factor_value_kinds: tuple[str, ...] = (),
        intended_uses: tuple[str, ...] = (),
        allowed_scopes: tuple[str, ...] = (),
        reference_year: int | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        normalized = _normalize_search_text(query)
        normalized_scopes = tuple(_normalize_search_text(scope) for scope in allowed_scopes)
        async with self._sessions() as session:
            if concept_codes:
                concept_matches = (
                    await session.execute(
                        select(ConceptRow.id.label("concept_id"), ConceptRow.code).where(
                            ConceptRow.code.in_(concept_codes), ConceptRow.active.is_(True)
                        )
                    )
                ).all()
            else:
                concept_matches = (
                    await session.execute(
                        select(
                            ConceptLabelRow.concept_id,
                            ConceptRow.code,
                            func.similarity(ConceptLabelRow.normalized_label, normalized),
                        )
                        .join(ConceptRow, ConceptRow.id == ConceptLabelRow.concept_id)
                        .where(
                            ConceptLabelRow.review_status == "approved",
                            or_(
                                ConceptLabelRow.normalized_label == normalized,
                                ConceptLabelRow.normalized_label.op("%")(normalized),
                            ),
                        )
                        .order_by(
                            func.similarity(ConceptLabelRow.normalized_label, normalized).desc()
                        )
                        .limit(20)
                    )
                ).all()
            scores: dict[UUID, float] = {}
            version_concept_codes: dict[UUID, str] = {}
            concept_ids = tuple({row.concept_id for row in concept_matches})
            if concept_ids:
                concept_statement = (
                    select(FactorVersionRow.id, ConceptRow.code)
                    .join(FactorRow, FactorRow.id == FactorVersionRow.factor_id)
                    .join(
                        DatasetVersionRow,
                        DatasetVersionRow.id == FactorVersionRow.dataset_version_id,
                    )
                    .join(FactorConceptRow, FactorConceptRow.factor_id == FactorRow.id)
                    .join(ConceptRow, ConceptRow.id == FactorConceptRow.concept_id)
                    .where(
                        DatasetVersionRow.status == DatasetVersionStatus.PUBLISHED.value,
                        FactorVersionRow.version_status == TemporalVersionStatus.CURRENT.value,
                        FactorConceptRow.concept_id.in_(concept_ids),
                    )
                )
                if entity_types:
                    concept_statement = concept_statement.where(
                        FactorVersionRow.entity_type.in_(entity_types)
                    )
                if factor_value_kinds:
                    concept_statement = concept_statement.where(
                        FactorVersionRow.factor_value_kind.in_(factor_value_kinds)
                    )
                if intended_uses:
                    concept_statement = concept_statement.where(
                        FactorVersionRow.intended_use.in_(intended_uses)
                    )
                if normalized_scopes:
                    concept_statement = concept_statement.where(
                        func.replace(
                            func.lower(FactorVersionRow.methodology["scope"].as_string()),
                            "_",
                            " ",
                        ).in_(normalized_scopes)
                    )
                if geography_codes:
                    concept_statement = concept_statement.where(
                        or_(
                            *(
                                type_coerce(
                                    FactorVersionRow.applicable_geographies, JSONB
                                ).contains([{"code": code}])
                                for code in geography_codes
                            )
                        )
                    )
                concept_statement = concept_statement.order_by(
                    FactorVersionRow.reference_year.desc().nullslast(),
                    FactorRow.logical_id,
                    FactorVersionRow.id,
                ).limit(limit)
                concept_factor_rows = (await session.execute(concept_statement)).all()
                for version_id, concept_code in concept_factor_rows:
                    scores[version_id] = max(scores.get(version_id, 0), 1.0)
                    version_concept_codes[version_id] = concept_code

            profile_filter = ""
            if entity_types:
                profile_filter += " AND fv.entity_type = ANY(CAST(:entity_types AS text[]))"
            if factor_value_kinds:
                profile_filter += (
                    " AND fv.factor_value_kind = ANY(CAST(:factor_value_kinds AS text[]))"
                )
            if intended_uses:
                profile_filter += " AND fv.intended_use = ANY(CAST(:intended_uses AS text[]))"
            if normalized_scopes:
                profile_filter += (
                    " AND replace(lower(coalesce(fv.methodology->>'scope', '')), '_', ' ') "
                    "= ANY(CAST(:allowed_scopes AS text[]))"
                )
            profile_parameters = {
                "entity_types": list(entity_types),
                "factor_value_kinds": list(factor_value_kinds),
                "intended_uses": list(intended_uses),
                "allowed_scopes": list(normalized_scopes),
            }

            fts_rows: Sequence[Any] = ()
            geography_filter = (
                """AND EXISTS (
                           SELECT 1
                           FROM jsonb_array_elements(fv.applicable_geographies) AS geo
                           WHERE upper(geo->>'code') = ANY(CAST(:geography_codes AS text[]))
                         )"""
                if geography_codes
                else ""
            )
            fts_rows = (
                await session.execute(
                    text(
                        f"""
                        SELECT fv.id,
                               ts_rank_cd(
                                 to_tsvector(
                                   'simple',
                                   regexp_replace(
                                     coalesce(fv.name, '') || ' ' ||
                                     coalesce(fv.description, '') || ' ' ||
                                     coalesce(fv.taxonomy_code, '') || ' ' ||
                                     coalesce(fv.activity_type, '') || ' ' ||
                                     coalesce(fv.applicable_geographies::text, '') || ' ' ||
                                     coalesce(fv.geography_roles::text, ''),
                                     '[^[:alnum:]]+', ' ', 'g'
                                   )
                                 ),
                                 websearch_to_tsquery('simple', :query)
                               ) AS score
                        FROM atlas_factor_versions AS fv
                        JOIN atlas_dataset_versions AS dv
                          ON dv.id = fv.dataset_version_id
                        WHERE dv.status = :published
                          AND fv.version_status = :current
                          {geography_filter}
                          {profile_filter}
                          AND to_tsvector(
                                'simple',
                                regexp_replace(
                                  coalesce(fv.name, '') || ' ' ||
                                  coalesce(fv.description, '') || ' ' ||
                                  coalesce(fv.taxonomy_code, '') || ' ' ||
                                  coalesce(fv.activity_type, '') || ' ' ||
                                  coalesce(fv.applicable_geographies::text, '') || ' ' ||
                                  coalesce(fv.geography_roles::text, ''),
                                  '[^[:alnum:]]+', ' ', 'g'
                                )
                              ) @@ websearch_to_tsquery('simple', :query)
                        ORDER BY score DESC
                        LIMIT :limit
                        """
                    ),
                    {
                        "query": normalized,
                        "published": DatasetVersionStatus.PUBLISHED.value,
                        "current": TemporalVersionStatus.CURRENT.value,
                        "limit": limit,
                        "geography_codes": list(geography_codes),
                        **profile_parameters,
                    },
                )
            ).all()
            for version_id, score in fts_rows:
                scores[version_id] = max(scores.get(version_id, 0), float(score or 0))

            trigram_rows: Sequence[Any] = ()
            if len(fts_rows) < limit:
                geography_filter = (
                    """AND EXISTS (
                           SELECT 1
                           FROM jsonb_array_elements(fv.applicable_geographies) AS geo
                           WHERE upper(geo->>'code') = ANY(CAST(:geography_codes AS text[]))
                         )"""
                    if geography_codes
                    else ""
                )
                trigram_rows = (
                    await session.execute(
                        text(
                            f"""
                            SELECT fv.id, 1.0 - (fv.name <-> :query) AS score
                            FROM atlas_factor_versions AS fv
                            JOIN atlas_dataset_versions AS dv
                              ON dv.id = fv.dataset_version_id
                            WHERE dv.status = :published
                              AND fv.version_status = :current
                              {geography_filter}
                              {profile_filter}
                              AND fv.name % :query
                            ORDER BY fv.name <-> :query
                            LIMIT :limit
                            """
                        ),
                        {
                            "query": normalized,
                            "published": DatasetVersionStatus.PUBLISHED.value,
                            "current": TemporalVersionStatus.CURRENT.value,
                            "limit": limit,
                            "geography_codes": list(geography_codes),
                            **profile_parameters,
                        },
                    )
                ).all()
            for version_id, score in trigram_rows:
                scores[version_id] = max(scores.get(version_id, 0), float(score or 0))

            selected_ids = tuple(
                version_id
                for version_id, _ in sorted(
                    scores.items(), key=lambda item: (-item[1], str(item[0]))
                )[:limit]
            )
            if not selected_ids:
                return []
            hydration_rows = (
                await session.execute(
                    select(
                        FactorRow,
                        FactorVersionRow,
                        SourceRow,
                        FactorSectorAssignmentRow,
                    )
                    .join(FactorVersionRow, FactorVersionRow.factor_id == FactorRow.id)
                    .join(SourceRow, SourceRow.id == FactorRow.source_id)
                    .outerjoin(
                        FactorSectorAssignmentRow,
                        FactorSectorAssignmentRow.factor_version_id == FactorVersionRow.id,
                    )
                    .where(FactorVersionRow.id.in_(selected_ids))
                )
            ).all()
            by_version = {
                version.id: (logical, version, source, sector)
                for logical, version, source, sector in hydration_rows
            }
            closest: dict[
                str,
                tuple[tuple[int, int, int, int, int], int, dict[str, Any]],
            ] = {}
            for rank, version_id in enumerate(selected_ids):
                logical, version, source, sector = by_version[version_id]
                payload = self._factor_payload(logical, version, source, sector)
                payload["concept_code"] = version_concept_codes.get(version_id)
                candidate_year = version.reference_year
                temporal_key = _reference_year_preference(reference_year, candidate_year, rank)
                current = closest.get(logical.logical_id)
                if current is None or temporal_key < current[0]:
                    closest[logical.logical_id] = (temporal_key, rank, payload)
            return [item[2] for item in sorted(closest.values(), key=lambda item: item[1])]

    async def get_published_factor(
        self,
        logical_id: str,
        *,
        reference_year: int | None = None,
        known_at: datetime | None = None,
    ) -> dict[str, Any] | None:
        async with self._sessions() as session:
            statement = (
                select(
                    FactorRow,
                    FactorVersionRow,
                    SourceRow,
                    FactorSectorAssignmentRow,
                )
                .join(FactorVersionRow, FactorVersionRow.factor_id == FactorRow.id)
                .join(
                    DatasetVersionRow,
                    DatasetVersionRow.id == FactorVersionRow.dataset_version_id,
                )
                .join(SourceRow, SourceRow.id == FactorRow.source_id)
                .outerjoin(
                    FactorSectorAssignmentRow,
                    FactorSectorAssignmentRow.factor_version_id == FactorVersionRow.id,
                )
                .where(
                    FactorRow.logical_id == logical_id,
                    DatasetVersionRow.status == DatasetVersionStatus.PUBLISHED.value,
                )
                .order_by(
                    FactorVersionRow.reference_year.desc().nullslast(),
                    FactorVersionRow.system_effective_from.desc().nullslast(),
                )
                .limit(1)
            )
            if reference_year is not None:
                statement = statement.where(FactorVersionRow.reference_year == reference_year)
            if known_at is None:
                statement = statement.where(
                    FactorVersionRow.version_status == TemporalVersionStatus.CURRENT.value
                )
            else:
                statement = statement.where(
                    FactorVersionRow.system_effective_from <= known_at,
                    or_(
                        FactorVersionRow.system_effective_to.is_(None),
                        FactorVersionRow.system_effective_to > known_at,
                    ),
                )
            row = (await session.execute(statement)).first()
            if row is None:
                return None
            logical, version, source, sector = row
            payload = self._factor_payload(logical, version, source, sector)
            payload["concept_code"] = await session.scalar(
                select(ConceptRow.code)
                .join(FactorConceptRow, FactorConceptRow.concept_id == ConceptRow.id)
                .where(FactorConceptRow.factor_id == logical.id)
                .order_by(ConceptRow.code)
                .limit(1)
            )
            provenance = list(
                await session.scalars(
                    select(ProvenanceRow)
                    .where(ProvenanceRow.factor_version_id == version.id)
                    .order_by(ProvenanceRow.role)
                )
            )
            payload["provenance"] = [
                {
                    "role": item.role,
                    "sheet": item.sheet,
                    "row": item.row_number,
                    "column_number": item.column_number,
                    "column_name": item.column_name,
                    "original_factor_name": item.original_factor_name,
                    "original_unit": item.original_unit,
                    "parser_version": item.parser_version,
                    "mapping_version": item.mapping_version,
                }
                for item in provenance
            ]
            return payload

    async def factor_versions(self, logical_id: str) -> list[dict[str, Any]]:
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(
                        FactorRow,
                        FactorVersionRow,
                        SourceRow,
                        FactorSectorAssignmentRow,
                    )
                    .join(FactorVersionRow, FactorVersionRow.factor_id == FactorRow.id)
                    .join(
                        DatasetVersionRow,
                        DatasetVersionRow.id == FactorVersionRow.dataset_version_id,
                    )
                    .join(SourceRow, SourceRow.id == FactorRow.source_id)
                    .outerjoin(
                        FactorSectorAssignmentRow,
                        FactorSectorAssignmentRow.factor_version_id == FactorVersionRow.id,
                    )
                    .where(
                        FactorRow.logical_id == logical_id,
                        DatasetVersionRow.status == DatasetVersionStatus.PUBLISHED.value,
                    )
                    .order_by(
                        FactorVersionRow.reference_year,
                        FactorVersionRow.system_effective_from,
                    )
                )
            ).all()
            return [
                self._factor_payload(logical, version, source, sector)
                for logical, version, source, sector in rows
            ]

    async def _activate_version(
        self,
        session: AsyncSession,
        version: DatasetVersionRow,
        dataset: DatasetRow,
        source: SourceRow | None,
    ) -> None:
        now = utc_now()
        release_filter = (
            DatasetVersionRow.release_year.is_(None)
            if version.release_year is None
            else DatasetVersionRow.release_year == version.release_year
        )
        previous_dataset = await session.scalar(
            select(DatasetVersionRow)
            .where(
                DatasetVersionRow.dataset_id == dataset.id,
                DatasetVersionRow.id != version.id,
                DatasetVersionRow.version_status == TemporalVersionStatus.CURRENT.value,
                release_filter,
            )
            .order_by(DatasetVersionRow.system_effective_from.desc().nullslast())
            .limit(1)
            .with_for_update()
        )
        if previous_dataset is not None:
            previous_dataset.version_status = TemporalVersionStatus.SUPERSEDED.value
            previous_dataset.system_effective_to = now
            previous_dataset.superseded_at = now
            version.supersedes_version_id = previous_dataset.id

        new_factor_versions = list(
            await session.scalars(
                select(FactorVersionRow).where(FactorVersionRow.dataset_version_id == version.id)
            )
        )
        temporal_keys = {
            (
                item.factor_id,
                item.reference_year,
                item.valid_from,
                item.valid_to,
            )
            for item in new_factor_versions
        }
        if len(temporal_keys) != len(new_factor_versions):
            raise ValueError("dataset contains duplicate logical factor temporal versions")

        previous_by_new: list[tuple[FactorVersionRow, FactorVersionRow]] = []
        for new_factor in new_factor_versions:
            reference_filter = (
                FactorVersionRow.reference_year.is_(None)
                if new_factor.reference_year is None
                else FactorVersionRow.reference_year == new_factor.reference_year
            )
            valid_from_filter = (
                FactorVersionRow.valid_from.is_(None)
                if new_factor.valid_from is None
                else FactorVersionRow.valid_from == new_factor.valid_from
            )
            valid_to_filter = (
                FactorVersionRow.valid_to.is_(None)
                if new_factor.valid_to is None
                else FactorVersionRow.valid_to == new_factor.valid_to
            )
            previous_factor = await session.scalar(
                select(FactorVersionRow)
                .where(
                    FactorVersionRow.factor_id == new_factor.factor_id,
                    FactorVersionRow.id != new_factor.id,
                    FactorVersionRow.version_status == TemporalVersionStatus.CURRENT.value,
                    reference_filter,
                    valid_from_filter,
                    valid_to_filter,
                )
                .order_by(FactorVersionRow.system_effective_from.desc().nullslast())
                .limit(1)
                .with_for_update()
            )
            if previous_factor is not None:
                previous_factor.version_status = TemporalVersionStatus.SUPERSEDED.value
                previous_factor.system_effective_to = now
                previous_factor.superseded_at = now
                previous_by_new.append((new_factor, previous_factor))

        covered_reference_years = {
            item.reference_year for item in new_factor_versions if item.reference_year is not None
        }
        if covered_reference_years and source is not None:
            previous_current_versions = list(
                await session.scalars(
                    select(FactorVersionRow)
                    .join(FactorRow, FactorRow.id == FactorVersionRow.factor_id)
                    .where(
                        FactorRow.source_id == source.id,
                        FactorVersionRow.dataset_version_id != version.id,
                        FactorVersionRow.version_status == TemporalVersionStatus.CURRENT.value,
                        FactorVersionRow.reference_year.in_(covered_reference_years),
                    )
                    .with_for_update()
                )
            )
            replacement_keys = {
                (item.factor_id, item.reference_year, item.valid_from, item.valid_to)
                for item in new_factor_versions
            }
            replaced_ids = {previous.id for _, previous in previous_by_new}
            for previous_factor in previous_current_versions:
                previous_key = (
                    previous_factor.factor_id,
                    previous_factor.reference_year,
                    previous_factor.valid_from,
                    previous_factor.valid_to,
                )
                if previous_factor.id in replaced_ids or previous_key in replacement_keys:
                    continue
                previous_factor.version_status = TemporalVersionStatus.SUPERSEDED.value
                previous_factor.system_effective_to = now
                previous_factor.superseded_at = now

        # Flush closures before opening the replacement periods so PostgreSQL's
        # partial unique indexes never observe two current versions.
        await session.flush()
        version.status = DatasetVersionStatus.PUBLISHED.value
        version.published_at = now
        version.version_status = TemporalVersionStatus.CURRENT.value
        version.system_effective_from = now
        version.system_effective_to = None
        for new_factor in new_factor_versions:
            new_factor.version_status = TemporalVersionStatus.CURRENT.value
            new_factor.system_effective_from = now
            new_factor.system_effective_to = None
        for new_factor, previous_factor in previous_by_new:
            new_factor.supersedes_version_id = previous_factor.id
        await session.flush()

        current_dataset = await session.scalar(
            select(DatasetVersionRow)
            .where(
                DatasetVersionRow.dataset_id == dataset.id,
                DatasetVersionRow.version_status == TemporalVersionStatus.CURRENT.value,
            )
            .order_by(
                DatasetVersionRow.release_year.desc().nullslast(),
                DatasetVersionRow.source_published_at.desc().nullslast(),
                DatasetVersionRow.system_effective_from.desc().nullslast(),
            )
            .limit(1)
        )
        dataset.current_version_id = (
            current_dataset.id if current_dataset is not None else version.id
        )
        if source is not None:
            source.last_successful_import_at = now
            source.health = "healthy"

    async def seed_taxonomy(self, mappings: dict[str, str], version: str) -> None:
        async with self._sessions.begin() as session:
            for code, name in mappings.items():
                existing = await session.scalar(select(TaxonomyRow).where(TaxonomyRow.code == code))
                if existing is None:
                    session.add(TaxonomyRow(code=code, name=name, version=version))

    @staticmethod
    def retry_delay(attempt: int) -> timedelta:
        delays = {1: timedelta(seconds=30), 2: timedelta(minutes=5), 3: timedelta(minutes=30)}
        return delays.get(attempt, timedelta(minutes=30))

    @staticmethod
    def _release_year(context: PipelineContext) -> int | None:
        explicit = context.metrics.get("release_year")
        if explicit is not None:
            return explicit
        years = {
            factor.reference_year for factor in context.normalized_factors if factor.reference_year
        }
        return next(iter(years)) if len(years) == 1 else None

    @staticmethod
    def _factor_payload(
        logical: FactorRow,
        version: FactorVersionRow,
        source: SourceRow,
        sector: FactorSectorAssignmentRow | None = None,
    ) -> dict[str, Any]:
        payload = {
            "factor_id": logical.logical_id,
            "cursor": (f"{logical.logical_id}|{version.reference_year or ''}|{version.id}"),
            "factor_version_id": str(version.id),
            "dataset_version_id": str(version.dataset_version_id),
            "source_code": source.code,
            "source_health": source.health,
            "source_factor_id": version.source_factor_id,
            "name": version.name,
            "taxonomy_code": version.taxonomy_code,
            "activity_type": version.activity_type,
            "activity_unit": version.activity_unit,
            "factor_value": str(version.factor_value),
            "factor_unit": version.factor_unit,
            "entity_type": version.entity_type,
            "factor_value_kind": version.factor_value_kind,
            "intended_use": version.intended_use,
            "default_match_eligible": (
                version.entity_type in {"emission_factor", "implied_emission_factor"}
                and version.factor_value_kind == "co2e_total"
                and version.intended_use == "inventory"
            ),
            "gases": version.gases,
            "origin_geography": version.origin_geography,
            "applicable_geographies": version.applicable_geographies,
            "geography_roles": version.geography_roles,
            "geography_level": version.geography_level,
            "geographic_specificity": version.geographic_specificity,
            "geographic_fit_type": version.geographic_fit_type,
            "reference_year": version.reference_year,
            "valid_from": version.valid_from,
            "valid_to": version.valid_to,
            "published_at": version.source_published_at,
            "retrieved_at": version.retrieved_at,
            "effective_from": version.system_effective_from,
            "effective_to": version.system_effective_to,
            "superseded_at": version.superseded_at,
            "supersedes_version_id": (
                str(version.supersedes_version_id)
                if version.supersedes_version_id is not None
                else None
            ),
            "version_status": version.version_status,
            "methodology": version.methodology,
            "data_quality": version.data_quality,
        }
        payload["sector"] = (
            AtlasRepository._sector_assignment_payload(sector) if sector is not None else None
        )
        return payload

    @staticmethod
    def _validate_run_target(source: SourceRow, requested_reference_year: int | None) -> RunMode:
        if requested_reference_year is None:
            return RunMode.LATEST
        history = source.manifest.get("history", {})
        strategy = SourceHistoryStrategy(history.get("strategy"))
        if strategy not in {
            SourceHistoryStrategy.YEARLY_RELEASE,
            SourceHistoryStrategy.LAGGED_YEARLY_RELEASE,
            SourceHistoryStrategy.YEARLY_SUBMISSION,
        }:
            raise ValueError(
                f"{source.code} uses {strategy.value.replace('_', ' ')}; "
                "request a latest snapshot, not a year"
            )
        start_year = int(history["start_year"])
        end_year = int(history["end_year"])
        if not start_year <= requested_reference_year <= end_year:
            raise ValueError(
                f"reference year {requested_reference_year} is outside "
                f"{source.code} coverage {start_year}-{end_year}"
            )
        schema = next(
            (
                item
                for item in history.get("schemas", [])
                if int(item["start_year"]) <= requested_reference_year <= int(item["end_year"])
            ),
            None,
        )
        if schema is None:
            raise ValueError(
                f"no parser schema is registered for {source.code} {requested_reference_year}"
            )
        if not bool(schema.get("implemented", True)):
            raise ValueError(
                f"parser schema {schema['name']} is not implemented for "
                f"{source.code} {requested_reference_year}"
            )
        return RunMode.HISTORICAL_BACKFILL

    @staticmethod
    async def _source_for_update(session: AsyncSession, source_code: str) -> SourceRow:
        source = await session.scalar(
            select(SourceRow).where(SourceRow.code == source_code.upper()).with_for_update()
        )
        if source is None:
            raise LookupError(source_code)
        if source.status != "active":
            raise ValueError(f"source is not active: {source_code}")
        return source


class SqlRunRepository(RunRepository):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def save(self, run: PipelineRun) -> None:
        async with self._sessions.begin() as session:
            row = await session.get(SourceRunRow, run.id, with_for_update=True)
            if row is None:
                return
            row.outcome = run.outcome.value
            row.run_mode = run.run_mode.value
            row.requested_reference_year = run.requested_reference_year
            row.requested_revision = run.requested_revision
            row.attempt = max(
                row.attempt,
                max((step.attempt for step in run.steps.values()), default=0),
            )
            row.failure_retryable = run.failure_retryable
            row.error_class = run.error_class
            row.finished_at = run.finished_at
            if row.started_at is None and any(step.started_at for step in run.steps.values()):
                row.started_at = min(
                    step.started_at for step in run.steps.values() if step.started_at is not None
                )
            step_rows = {
                item.step: item
                for item in await session.scalars(
                    select(RunStepRow).where(RunStepRow.run_id == run.id)
                )
            }
            for step, state in run.steps.items():
                persisted = step_rows.get(step.value)
                if persisted is None:
                    persisted = RunStepRow(
                        run_id=run.id,
                        step=step.value,
                        status=state.status.value,
                    )
                    session.add(persisted)
                persisted.status = state.status.value
                persisted.attempt = state.attempt
                persisted.started_at = state.started_at
                persisted.finished_at = state.finished_at
                persisted.message = state.message
