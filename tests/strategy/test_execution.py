import pytest
from decimal import Decimal

from services.strategy import (
    OrderMapper,
    SignalGenerator,
    SignalType,
)


def test_order_mapping():
    generator = SignalGenerator()

    signal = generator.generate(
        strategy_id="demo",
        symbol="AAPL",
        signal=SignalType.BUY,
        confidence=0.9,
        reason="test",
    )

    mapper = OrderMapper()

    command = mapper.map(signal)

    assert command.symbol == "AAPL"
    assert command.side == "BUY"
    assert command.quantity == Decimal("1")


def test_order_mapping_sell():
    generator = SignalGenerator()

    signal = generator.generate(
        strategy_id="demo",
        symbol="MSFT",
        signal=SignalType.SELL,
        confidence=0.8,
        reason="test",
    )

    mapper = OrderMapper()

    command = mapper.map(signal)

    assert command.symbol == "MSFT"
    assert command.side == "SELL"