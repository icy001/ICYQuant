import pytest
from datetime import datetime
from decimal import Decimal

from services.market_data.quote import Quote
from services.market_data.service import MarketDataService


class DummyCache:
    """The original InMemoryMarketCache was removed by the redis-cache
    commit (5d92613); the service only needs the repository protocol,
    so a plain dict stands in."""

    def __init__(self):
        self._quotes = {}

    async def save_quote(self, quote):
        self._quotes[quote.symbol] = quote

    async def get_quote(self, symbol):
        return self._quotes.get(symbol)


@pytest.mark.asyncio
async def test_market_cache():
    cache = DummyCache()
    service = MarketDataService(cache)

    quote = Quote(
        symbol="AAPL",
        bid=Decimal("210"),
        ask=Decimal("211"),
        last=Decimal("210.5"),
        timestamp=datetime.utcnow(),
    )

    await service.publish_quote(quote)

    latest = await service.latest_quote("AAPL")

    assert latest is not None
    assert latest.last == Decimal("210.5")


@pytest.mark.asyncio
async def test_market_cache_not_found():
    cache = DummyCache()
    service = MarketDataService(cache)

    latest = await service.latest_quote("UNKNOWN")

    assert latest is None


@pytest.mark.asyncio
async def test_market_cache_update():
    cache = DummyCache()
    service = MarketDataService(cache)

    quote1 = Quote(
        symbol="MSFT",
        bid=Decimal("378"),
        ask=Decimal("379"),
        last=Decimal("378.5"),
        timestamp=datetime.utcnow(),
    )

    quote2 = Quote(
        symbol="MSFT",
        bid=Decimal("379"),
        ask=Decimal("380"),
        last=Decimal("379.5"),
        timestamp=datetime.utcnow(),
    )

    await service.publish_quote(quote1)
    await service.publish_quote(quote2)

    latest = await service.latest_quote("MSFT")

    assert latest.last == Decimal("379.5")