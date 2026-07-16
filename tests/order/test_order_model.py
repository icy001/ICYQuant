from decimal import Decimal

from services.order import (
    Order,
    OrderSide,
)


def test_create_order():

    order = Order(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=Decimal("100"),
    )

    assert order.symbol == "AAPL"
    assert order.remaining_quantity == Decimal("100")
    assert not order.is_completed