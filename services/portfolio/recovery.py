"""
Portfolio recovery service.
"""

from __future__ import annotations

from .repository import PortfolioRepository


class PortfolioRecoveryService:
    def __init__(
        self,
        repository: PortfolioRepository,
    ):
        self.repository = repository

    async def recover(
        self,
        account_id: str,
    ):
        return await self.repository.load(account_id)