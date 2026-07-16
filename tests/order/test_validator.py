from decimal import Decimal

import pytest

from services.order import (
    InvalidPrice,
    InvalidQuantity,
    Order,
    OrderSide,
    OrderType,
    OrderValidator,
)


def test_market_order():

    order = Order(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=Decimal("100"),
    )

    OrderValidator.validate(order)


def test_invalid_quantity():

    order = Order(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=Decimal("0"),
    )

    with pytest.raises(InvalidQuantity):

        OrderValidator.validate(order)


def test_limit_order_requires_price():

    order = Order(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=Decimal("10"),
        order_type=OrderType.LIMIT,
    )

    with pytest.raises(InvalidPrice):

        OrderValidator.validate(order)


def test_valid_limit_order():

    order = Order(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=Decimal("10"),
        order_type=OrderType.LIMIT,
        limit_price=Decimal("180"),
    )

    OrderValidator.validate(order)