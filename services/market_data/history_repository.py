"""
Historical repository abstraction.
"""

from __future__ import annotations

from typing import Protocol

from .candle import Candle
from .query import HistoryQuery


class HistoricalRepository(Protocol):
    async def candles(
        self,
        query: HistoryQuery,
    ) -> list[Candle]:
        ...