from decimal import Decimal

from services.position import (
    PositionRebuildService,
)


class Trade:
    def __init__(
        self,
        quantity,
        price,
    ):
        self.quantity = quantity
        self.price = price


def test_position_rebuild():
    service = PositionRebuildService()

    snapshot = service.rebuild(
        account_id="ACC-001",
        symbol="AAPL",
        trades=[
            Trade(
                Decimal("100"),
                Decimal("100"),
            ),
            Trade(
                Decimal("-40"),
                Decimal("120"),
            ),
        ],
    )

    assert snapshot.quantity == Decimal("60")
    assert snapshot.realized_pnl == Decimal("800")