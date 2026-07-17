import pytest

from services.market_data import (
    MarketDataFacade,
    MarketHealthMonitor,
    MarketStatus,
)


class DummyRealtime:
    async def latest_quote(
        self,
        symbol,
    ):
        return symbol


class DummyHistory:
    async def candles(
        self,
        query,
    ):
        return []


@pytest.mark.asyncio
async def test_market_facade():
    facade = MarketDataFacade(
        DummyRealtime(),
        DummyHistory(),
    )

    result = await facade.latest_quote("AAPL")

    assert result == "AAPL"

    facade.health.mark_running()

    assert facade.health.status == MarketStatus.RUNNING


@pytest.mark.asyncio
async def test_market_facade_candles():
    facade = MarketDataFacade(
        DummyRealtime(),
        DummyHistory(),
    )

    candles = await facade.candles({"symbol": "MSFT"})

    assert candles == []


def test_health_monitor_status():
    monitor = MarketHealthMonitor()

    assert monitor.status == MarketStatus.STARTING

    monitor.mark_running()
    assert monitor.status == MarketStatus.RUNNING

    monitor.mark_degraded()
    assert monitor.status == MarketStatus.DEGRADED

    monitor.mark_stopped()
    assert monitor.status == MarketStatus.STOPPED