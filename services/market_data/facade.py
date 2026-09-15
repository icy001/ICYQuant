"""
Market facade.
"""

from __future__ import annotations

from .statistics import MarketStatistics
from .status import MarketStatus


class MarketHealthMonitor:
    # Restored from the original health module: the Commit 16 rewrite
    # repurposed services/market_data/health.py, so the legacy monitor
    # lives with its only consumer now.
    def __init__(self):
        self.status = MarketStatus.STARTING
        self.statistics = MarketStatistics()

    def mark_running(self):
        self.status = MarketStatus.RUNNING

    def mark_degraded(self):
        self.status = MarketStatus.DEGRADED

    def mark_stopped(self):
        self.status = MarketStatus.STOPPED


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