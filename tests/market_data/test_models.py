from datetime import datetime
from decimal import Decimal

from services.market_data import (
    Instrument,
    InstrumentType,
    MarketSnapshot,
    Quote,
    Tick,
    Candle,
)


def test_market_snapshot():
    instrument = Instrument(
        symbol="AAPL",
        exchange="NASDAQ",
        instrument_type=InstrumentType.STOCK,
    )

    quote = Quote(
        symbol="AAPL",
        bid=Decimal("210.10"),
        ask=Decimal("210.15"),
        last=Decimal("210.12"),
        timestamp=datetime.utcnow(),
    )

    snapshot = MarketSnapshot(
        instrument=instrument,
        quote=quote,
    )

    assert snapshot.instrument.symbol == "AAPL"
    assert snapshot.quote.last == Decimal("210.12")


def test_tick():
    tick = Tick(
        symbol="MSFT",
        price=Decimal("378.50"),
        quantity=Decimal("100"),
        timestamp=datetime.utcnow(),
    )

    assert tick.symbol == "MSFT"
    assert tick.price == Decimal("378.50")


def test_candle():
    candle = Candle(
        symbol="GOOG",
        open=Decimal("141.00"),
        high=Decimal("142.50"),
        low=Decimal("140.80"),
        close=Decimal("142.10"),
        volume=Decimal("1500000"),
        timestamp=datetime.utcnow(),
    )

    assert candle.close == Decimal("142.10")
    assert candle.high >= candle.low