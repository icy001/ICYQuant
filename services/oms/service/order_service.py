from typing import Dict, Optional

from contracts.events.order_event import OrderCreatedEvent, OrderFilledEvent, OrderCancelledEvent
from services.oms.domain.order import Order
from services.oms.domain.order_state import OrderSide, OrderType
from services.oms.repository.order_repository import OrderRepository


class OrderService:
    def __init__(self) -> None:
        self.repository = OrderRepository()

    def create_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float = 0.0,
        order_type: str = "MARKET",
    ) -> Order:
        order = Order(
            symbol=symbol,
            side=OrderSide(side),
            quantity=quantity,
            price=price,
            order_type=OrderType(order_type),
        )

        self.repository.save(order)

        event = OrderCreatedEvent(
            event_id=order.id,
            symbol=order.symbol,
            side=order.side.value,
            quantity=order.quantity,
            price=order.price,
        )

        return order

    def submit_order(self, order_id: str) -> Optional[Order]:
        order = self.repository.get(order_id)
        if order:
            order.submit()
            self.repository.save(order)
        return order

    def accept_order(self, order_id: str) -> Optional[Order]:
        order = self.repository.get(order_id)
        if order:
            order.accept()
            self.repository.save(order)
        return order

    def fill_order(self, order_id: str, quantity: float = None) -> Optional[Order]:
        order = self.repository.get(order_id)
        if order:
            order.fill(quantity)
            self.repository.save(order)

            event = OrderFilledEvent(
                event_id=order.id,
                symbol=order.symbol,
                quantity=order.quantity,
                price=order.price,
            )
        return order

    def cancel_order(self, order_id: str) -> Optional[Order]:
        order = self.repository.get(order_id)
        if order:
            order.cancel()
            self.repository.save(order)

            event = OrderCancelledEvent(
                event_id=order.id,
                symbol=order.symbol,
            )
        return order

    def get_order(self, order_id: str) -> Optional[Order]:
        return self.repository.get(order_id)

    def get_orders_by_symbol(self, symbol: str) -> list:
        return self.repository.get_by_symbol(symbol)

    def get_all_orders(self) -> list:
        return self.repository.get_all()
