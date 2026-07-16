"""
Order mapper.

Convert between domain model and ORM model.
"""

from __future__ import annotations

from .model import Order
from .orm import OrderModel


class OrderMapper:

    @staticmethod
    def to_model(
        order: Order,
    ) -> OrderModel:

        return OrderModel(
            id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            status=order.status,
            time_in_force=order.time_in_force,
            quantity=order.quantity,
            filled_quantity=order.filled_quantity,
            average_price=order.average_price,
            limit_price=order.limit_price,
            stop_price=order.stop_price,
        )

    @staticmethod
    def to_domain(
        model: OrderModel,
    ) -> Order:

        order = Order(
            symbol=model.symbol,
            side=model.side,
            quantity=model.quantity,
            order_type=model.order_type,
            limit_price=model.limit_price,
            stop_price=model.stop_price,
            time_in_force=model.time_in_force,
        )

        order.order_id = model.id
        order.status = model.status
        order.filled_quantity = model.filled_quantity
        order.average_price = model.average_price
        order.created_at = model.created_at
        order.updated_at = model.updated_at

        return order