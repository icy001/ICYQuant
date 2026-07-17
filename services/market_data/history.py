"""
Historical market data service.
"""

from __future__ import annotations

from .history_repository import HistoricalRepository
from .query import HistoryQuery


class HistoricalMarketDataService:
    def __init__(
        self,
        repository: HistoricalRepository,
    ):
        self.repository = repository

    async def candles(
        self,
        query: HistoryQuery,
    ):
        return await self.repository.candles(query)