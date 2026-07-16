"""
General ledger query service.
"""

from __future__ import annotations

from .queries import JournalQuery


class LedgerQueryService:
    def __init__(
        self,
        repository,
    ) -> None:
        self.repository = repository

    async def find_by_reference(
        self,
        reference_type: str,
        reference_id: str,
    ):
        return await self.repository.list_by_reference(
            reference_type=reference_type,
            reference_id=reference_id,
        )

    async def execute(
        self,
        query: JournalQuery,
    ):
        return await self.repository.search(
            query
        )