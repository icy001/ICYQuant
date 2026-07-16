"""
Ledger repository interfaces.
"""

from __future__ import annotations

from typing import Optional, Protocol

from .journal import Journal


class JournalRepositoryProtocol(
    Protocol,
):
    async def save(
        self,
        journal: Journal,
    ) -> None:
        ...

    async def find(
        self,
        journal_id: str,
    ) -> Optional[Journal]:
        ...

    async def list_by_reference(
        self,
        reference_type: str,
        reference_id: str,
    ) -> list[Journal]:
        ...