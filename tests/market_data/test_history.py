import pytest
from datetime import datetime
from decimal import Decimal

from services.market_data.candle import Candle
from services.market_data.history import HistoricalMarketDataService
from services.market_data.query import HistoryQuery


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