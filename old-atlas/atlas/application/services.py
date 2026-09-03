from __future__ import annotations

from uuid import UUID

from atlas.infrastructure.database.repositories import AtlasRepository, RunRequest


class AtlasApplication:
    def __init__(self, repository: AtlasRepository) -> None:
        self.repository = repository

    async def request_source_run(
        self,
        source_code: str,
        requested_by: str,
        requested_reference_year: int | None = None,
    ) -> RunRequest:
        return await self.repository.request_run(
            source_code,
            requested_by,
            requested_reference_year,
        )

    async def approve_review(
        self, review_id: UUID, *, decided_by: str, note: str | None = None
    ) -> None:
        await self.repository.approve_review(review_id, decided_by, note)

    async def reject_review(
        self, review_id: UUID, *, decided_by: str, note: str | None = None
    ) -> None:
        await self.repository.reject_review(review_id, decided_by, note)
