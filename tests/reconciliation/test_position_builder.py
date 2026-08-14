from dataclasses import dataclass
from decimal import Decimal

from services.reconciliation.models.execution_position import ExecutionPosition
from services.reconciliation.position_builder import ExecutionPositionBuilder


@dataclass(frozen=True)
class FillEvent:
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal


def make_event(side, quantity, price, symbol="AAPL"):
    return FillEvent(
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
    )


def test_build_accumulates_buy_position():
    events = [
        make_event("BUY", Decimal("100"), Decimal("150")),
        make_event("BUY", Decimal("100"), Decimal("170")),
    ]

    position = ExecutionPositionBuilder().build(events)

    assert isinstance(position, ExecutionPosition)
    assert position.symbol == "AAPL"
    assert position.quantity == Decimal("200")
    assert position.average_price == Decimal("160")
    assert position.realized_pnl == Decimal("0")


def test_build_realizes_pnl_on_partial_sell():
    events = [
        make_event("BUY", Decimal("100"), Decimal("100")),
        make_event("SELL", Decimal("40"), Decimal("120")),
    ]

    position = ExecutionPositionBuilder().build(events)

    assert position.quantity == Decimal("60")
    assert position.average_price == Decimal("100")
    assert position.realized_pnl == Decimal("800")


def test_build_empty_events_creates_zero_position():
    position = ExecutionPositionBuilder().build([])

    assert position.symbol == ""
    assert position.quantity == Decimal("0")
    assert position.average_price == Decimal("0")
    assert position.realized_pnl == Decimal("0")


def test_build_sell_only_creates_short_position():
    events = [make_event("SELL", Decimal("50"), Decimal("100"))]

    position = ExecutionPositionBuilder().build(events)

    assert position.quantity == Decimal("-50")
    assert position.average_price == Decimal("100")
    assert position.realized_pnl == Decimal("0")
