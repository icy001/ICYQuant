from decimal import Decimal

from services.position import (
    Position,
    PositionCalculator,
    PositionSide,
)


def test_position_side():
    assert (
        PositionCalculator.side(Decimal("100"))
        ==
        PositionSide.LONG
    )
    assert (
        PositionCalculator.side(Decimal("-1"))
        ==
        PositionSide.SHORT
    )
    assert (
        PositionCalculator.side(Decimal("0"))
        ==
        PositionSide.FLAT
    )


def test_position_defaults():
    position = Position(
        account_id="ACC-001",
        symbol="AAPL",
    )

    assert position.quantity == Decimal("0")
    assert position.average_cost == Decimal("0")