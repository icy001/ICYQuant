from decimal import Decimal

from services.position import (
    Position,
    PositionEngine,
)


def test_open_position():
    position = Position(
        account_id="ACC",
        symbol="AAPL",
    )

    engine = PositionEngine()

    engine.apply_trade(
        position,
        Decimal("100"),
        Decimal("100"),
    )

    assert position.quantity == Decimal("100")
    assert position.average_cost == Decimal("100")


def test_average_cost():
    position = Position(
        account_id="ACC",
        symbol="AAPL",
    )

    engine = PositionEngine()

    engine.apply_trade(
        position,
        Decimal("100"),
        Decimal("100"),
    )

    engine.apply_trade(
        position,
        Decimal("100"),
        Decimal("120"),
    )

    assert position.average_cost == Decimal("110")


def test_realized_pnl():
    position = Position(
        account_id="ACC",
        symbol="AAPL",
    )

    engine = PositionEngine()

    engine.apply_trade(
        position,
        Decimal("100"),
        Decimal("100"),
    )

    engine.apply_trade(
        position,
        Decimal("-50"),
        Decimal("120"),
    )

    assert position.realized_pnl == Decimal("1000")