import pytest
from datetime import datetime
from decimal import Decimal

from services.market_data import (
    InMemoryMarketCache,
    MarketFeedEngine,
    MarketPublisher,
    Quote,
    SubscriptionManager,
)


@pytest.mark.asyncio
async def test_feed():
    repository = InMemoryMarketCache()
    publisher = MarketPublisher(SubscriptionManager())
    engine = MarketFeedEngine(repository, publisher)

    quote = Quote(
        symbol="AAPL",
        bid=Decimal("100"),
        ask=Decimal("101"),
        last=Decimal("100.5"),
        timestamp=datetime.utcnow(),
    )

    ok = await engine.process(quote)

    assert ok
    assert engine.metrics.received == 1
    assert engine.metrics.published == 1


@pytest.mark.asyncio
async def test_feed_invalid_quote():
    repository = InMemoryMarketCache()
    publisher = MarketPublisher(SubscriptionManager())
    engine = MarketFeedEngine(repository, publisher)

    invalid_quote = Quote(
        symbol="MSFT",
        bid=Decimal("100"),
        ask=Decimal("99"),
        last=Decimal("99.5"),
        timestamp=datetime.utcnow(),
    )

    ok = await engine.process(invalid_quote)

    assert not ok
    assert engine.metrics.rejected == 1


@pytest.mark.asyncio
async def test_feed_cache_update():
    repository = InMemoryMarketCache()
    publisher = MarketPublisher(SubscriptionManager())
    engine = MarketFeedEngine(repository, publisher)

    quote1 = Quote(
        symbol="GOOG",
        bid=Decimal("140"),
        ask=Decimal("141"),
        last=Decimal("140.5"),
        timestamp=datetime.utcnow(),
    )

    quote2 = Quote(
        symbol="GOOG",
        bid=Decimal("141"),
        ask=Decimal("142"),
        last=Decimal("141.5"),
        timestamp=datetime.utcnow(),
    )

    await engine.process(quote1)
    await engine.process(quote2)

    assert engine.metrics.received == 2
    assert engine.metrics.published == 2

    cached = await repository.get_quote("GOOG")
    assert cached.last == Decimal("141.5")