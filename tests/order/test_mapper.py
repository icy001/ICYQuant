from decimal import Decimal

from services.order import (
    Order,
    OrderMapper,
    OrderSide,
)


def test_to_model():

    order = Order(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=Decimal("100"),
    )

    orm = OrderMapper.to_model(
        order
    )

    assert orm.symbol == "AAPL"
    assert orm.quantity == Decimal("100")


def test_to_domain():

    order = Order(
        symbol="MSFT",
        side=OrderSide.BUY,
        quantity=Decimal("50"),
    )

    orm = OrderMapper.to_model(
        order
    )

    domain = OrderMapper.to_domain(
        orm
    )

    assert domain.symbol == order.symbol
    assert domain.quantity == order.quantity
    assert domain.order_id == order.order_id