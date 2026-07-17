import pytest
from datetime import datetime
from decimal import Decimal

from services.market_data import (
    Candle,
    HistoricalMarketDataService,
    HistoryQuery,
    MarketReplay,
)


class DummyRepository:
    async def candles(
        self,
        query,
    ):
        return [
            Candle(
                symbol=query.symbol,
                open=Decimal("100"),
                high=Decimal("105"),
                low=Decimal("99"),
                close=Decimal("103"),
                volume=Decimal("10000"),
                timestamp=query.start,
            )
        ]


@pytest.mark.asyncio
async def test_history():
    service = HistoricalMarketDataService(DummyRepository())

    candles = await service.candles(
        HistoryQuery(
            symbol="AAPL",
            start=datetime.utcnow(),
            end=datetime.utcnow(),
        )
    )

    assert len(candles) == 1
    assert candles[0].symbol == "AAPL"


@pytest.mark.asyncio
async def test_replay():
    replay = MarketReplay()

    candles = [
        Candle(
            symbol="MSFT",
            open=Decimal("300"),
            high=Decimal("305"),
            low=Decimal("298"),
            close=Decimal("302"),
            volume=Decimal("5000"),
            timestamp=datetime.utcnow(),
        )
        for _ in range(3)
    ]

    received = []

    async def consumer(candle):
        received.append(candle)

    await replay.replay(candles, consumer)

    assert len(received) == 3