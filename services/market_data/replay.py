"""
Historical replay.
"""

from __future__ import annotations


class MarketReplay:
    async def replay(
        self,
        candles,
        consumer,
    ):
        for candle in candles:
            await consumer(candle)