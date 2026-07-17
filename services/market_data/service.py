"""
Market data service.
"""

from __future__ import annotations

from .repository import MarketDataRepository
from .quote import Quote


class MarketDataService:
    def __init__(
        self,
        repository: MarketDataRepository,
    ):
        self.repository = repository

    async def publish_quote(
        self,
        quote: Quote,
    ) -> None:
        await self.repository.save_quote(quote)

    async def latest_quote(
        self,
        symbol: str,
    ) -> Quote | None:
        return await self.repository.get_quote(symbol)