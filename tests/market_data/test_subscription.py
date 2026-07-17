import pytest
from datetime import datetime
from decimal import Decimal

from services.market_data import (
    MarketPublisher,
    Quote,
    SubscriptionManager,
)


class DummySubscriber:
    def __init__(self):
        self.last = None

    async def on_quote(
        self,
        quote,
    ):
        self.last = quote


@pytest.mark.asyncio
async def test_subscription():
    manager = SubscriptionManager()
    subscriber = DummySubscriber()
    manager.subscribe("AAPL", subscriber)

    publisher = MarketPublisher(manager)

    quote = Quote(
        symbol="AAPL",
        bid=Decimal("100"),
        ask=Decimal("101"),
        last=Decimal("100.5"),
        timestamp=datetime.utcnow(),
    )

    await publisher.publish_quote(quote)

    assert subscriber.last is not None
    assert subscriber.last.last == Decimal("100.5")


@pytest.mark.asyncio
async def test_multiple_subscribers():
    manager = SubscriptionManager()
    subscriber1 = DummySubscriber()
    subscriber2 = DummySubscriber()
    manager.subscribe("MSFT", subscriber1)
    manager.subscribe("MSFT", subscriber2)

    publisher = MarketPublisher(manager)

    quote = Quote(
        symbol="MSFT",
        bid=Decimal("378"),
        ask=Decimal("379"),
        last=Decimal("378.5"),
        timestamp=datetime.utcnow(),
    )

    await publisher.publish_quote(quote)

    assert subscriber1.last is not None
    assert subscriber2.last is not None


@pytest.mark.asyncio
async def test_unsubscribe():
    manager = SubscriptionManager()
    subscriber = DummySubscriber()
    manager.subscribe("GOOG", subscriber)
    manager.unsubscribe("GOOG", subscriber)

    publisher = MarketPublisher(manager)

    quote = Quote(
        symbol="GOOG",
        bid=Decimal("140"),
        ask=Decimal("141"),
        last=Decimal("140.5"),
        timestamp=datetime.utcnow(),
    )

    await publisher.publish_quote(quote)

    assert subscriber.last is None