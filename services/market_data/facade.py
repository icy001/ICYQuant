"""
Market facade.
"""

from __future__ import annotations

from .health import MarketHealthMonitor


class MarketDataFacade:
    def __init__(
        self,
        service,
        history,
    ):
        self.service = service
        self.history = history
        self.health = MarketHealthMonitor()

    async def latest_quote(
        self,
        symbol: str,
    ):
        return await self.service.latest_quote(symbol)

    async def candles(
        self,
        query,
    ):
        return await self.history.candles(query)