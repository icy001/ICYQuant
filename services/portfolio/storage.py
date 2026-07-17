"""
In-memory portfolio repository.
"""

from __future__ import annotations

from .model import Portfolio


class InMemoryPortfolioRepository:
    def __init__(self):
        self._storage: dict[str, Portfolio] = {}

    async def save(
        self,
        portfolio: Portfolio,
    ) -> None:
        self._storage[portfolio.account_id] = portfolio

    async def load(
        self,
        account_id: str,
    ) -> Portfolio | None:
        return self._storage.get(account_id)