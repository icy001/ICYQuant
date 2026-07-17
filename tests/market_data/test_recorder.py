import pytest
from datetime import datetime
from decimal import Decimal

from services.market_data import (
    MarketRecorder,
    Quote,
)


class DummyRecordingRepository:
    def __init__(self):
        self.items = []

    async def append_quote(
        self,
        quote,
    ):
        self.items.append(quote)


@pytest.mark.asyncio
async def test_recorder():
    repository = DummyRecordingRepository()
    recorder = MarketRecorder(repository)

    quote = Quote(
        symbol="AAPL",
        bid=Decimal("200"),
        ask=Decimal("201"),
        last=Decimal("200.5"),
        timestamp=datetime.utcnow(),
    )

    await recorder.record(quote)

    assert len(repository.items) == 1
    assert recorder.metrics.recorded == 1


@pytest.mark.asyncio
async def test_recorder_multiple_quotes():
    repository = DummyRecordingRepository()
    recorder = MarketRecorder(repository)

    quotes = [
        Quote(
            symbol="MSFT",
            bid=Decimal("300"),
            ask=Decimal("301"),
            last=Decimal("300.5"),
            timestamp=datetime.utcnow(),
        )
        for _ in range(3)
    ]

    for quote in quotes:
        await recorder.record(quote)

    assert len(repository.items) == 3
    assert recorder.metrics.recorded == 3


@pytest.mark.asyncio
async def test_recorder_failure():
    repository = DummyRecordingRepository()
    recorder = MarketRecorder(repository)

    async def failing_append(quote):
        raise RuntimeError("Storage failure")

    repository.append_quote = failing_append

    quote = Quote(
        symbol="GOOG",
        bid=Decimal("140"),
        ask=Decimal("141"),
        last=Decimal("140.5"),
        timestamp=datetime.utcnow(),
    )

    with pytest.raises(RuntimeError):
        await recorder.record(quote)

    assert recorder.metrics.failed == 1