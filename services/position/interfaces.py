"""
Position interfaces.
"""

from __future__ import annotations

from typing import Protocol

from .model import Position


class PositionRepositoryProtocol(
    Protocol,
):
    async def find(
        self,
        account_id: str,
        symbol: str,
    ) -> Position | None:
        ...

    async def upsert(
        self,
        position: Position,
    ) -> None:
        ...