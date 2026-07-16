"""
Order validator.
"""

from __future__ import annotations

from decimal import Decimal

from .enums import OrderType
from .exceptions import (
    InvalidOrderType,
    InvalidPrice,
    InvalidQuantity,
    InvalidSymbol,
)
from .model import Order


class OrderValidator:

    @staticmethod
    def validate(order: Order) -> None:

        OrderValidator.validate_symbol(order)

        OrderValidator.validate_quantity(order)

        OrderValidator.validate_price(order)

    @staticmethod
    def validate_symbol(order: Order) -> None:

        symbol = order.symbol.strip()

        if not symbol:
            raise InvalidSymbol(
                "symbol cannot be empty"
            )

    @staticmethod
    def validate_quantity(order: Order) -> None:

        if order.quantity <= Decimal("0"):
            raise InvalidQuantity(
                "quantity must be positive"
            )

    @staticmethod
    def validate_price(order: Order) -> None:

        if order.order_type == OrderType.MARKET:

            return

        if order.limit_price is None:

            raise InvalidPrice(
                "limit order requires limit_price"
            )

        if order.limit_price <= Decimal("0"):

            raise InvalidPrice(
                "limit_price must be positive"
            )

        if (
            order.order_type
            == OrderType.STOP_LIMIT
            and order.stop_price is None
        ):
            raise InvalidPrice(
                "stop_limit requires stop_price"
            )

        if (
            order.stop_price is not None
            and order.stop_price <= Decimal("0")
        ):
            raise InvalidPrice(
                "stop_price must be positive"
            )

    @staticmethod
    def validate_order_type(order: Order) -> None:

        if order.order_type not in OrderType:

            raise InvalidOrderType(
                "unsupported order type"
            )