"""
Portfolio repository abstraction.
"""

from __future__ import annotations

from typing import Protocol

from .model import Portfolio


class PortfolioRepository(Protocol):
    async def save(
        self,
        portfolio: Portfolio,
    ) -> None:
        ...

    async def load(
        self,
        account_id: str,
    ) -> Portfolio | None:
        ...