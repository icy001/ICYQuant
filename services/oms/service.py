from typing import Dict, Optional

from .models import Order
from .repository import OrderRepository
from .state import OrderStatus, OrderType


class OMSService:
    def __init__(self, repository: OrderRepository = None, risk_checker=None, execution_gateway=None) -> None:
        self.repository = repository or OrderRepository()
        self.risk_checker = risk_checker
        self.execution_gateway = execution_gateway

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
            side=side,
            quantity=quantity,
            price=price,
            order_type=OrderType(order_type),
        )

        self.repository.save(order)
        return order

    def submit(self, order_id: str, portfolio=None) -> Optional[Order]:
        order = self.repository.get(order_id)
        if not order:
            return None

        order.submit_to_risk()
        self.repository.save(order)

        if self.risk_checker and portfolio:
            risk_result = self.risk_checker.check(order, portfolio)
            order.risk_check_result = risk_result

            if not risk_result.get("overall", False):
                order.reject()
                self.repository.save(order)
                return order

        order.approve()
        self.repository.save(order)

        order.submit()
        self.repository.save(order)

        if self.execution_gateway:
            fill = self.execution_gateway.send_order(order)
            if fill:
                order.acknowledge()
                order.fill(fill.quantity)
                self.repository.save(order)

        return order

    def approve_order(self, order_id: str) -> Optional[Order]:
        order = self.repository.get(order_id)
        if order:
            order.approve()
            self.repository.save(order)
        return order

    def reject_order(self, order_id: str) -> Optional[Order]:
        order = self.repository.get(order_id)
        if order:
            order.reject()
            self.repository.save(order)
        return order

    def acknowledge_order(self, order_id: str) -> Optional[Order]:
        order = self.repository.get(order_id)
        if order:
            order.acknowledge()
            self.repository.save(order)
        return order

    def fill_order(self, order_id: str, quantity: float = None) -> Optional[Order]:
        order = self.repository.get(order_id)
        if order:
            order.fill(quantity)
            self.repository.save(order)
        return order

    def cancel_order(self, order_id: str) -> Optional[Order]:
        order = self.repository.get(order_id)
        if order:
            order.cancel()
            self.repository.save(order)
        return order

    def fail_order(self, order_id: str) -> Optional[Order]:
        order = self.repository.get(order_id)
        if order:
            order.fail()
            self.repository.save(order)
        return order

    def get_order(self, order_id: str) -> Optional[Order]:
        return self.repository.get(order_id)

    def get_orders_by_symbol(self, symbol: str) -> list:
        return self.repository.get_by_symbol(symbol)

    def get_all_orders(self) -> list:
        return self.repository.get_all()

    def get_orders_by_status(self, status: OrderStatus) -> list:
        return [order for order in self.repository.get_all() if order.status == status]

    def submit_order(self, order_id: str) -> Optional[Order]:
        return self.submit(order_id)

    def accept_order(self, order_id: str) -> Optional[Order]:
        order = self.repository.get(order_id)
        if order:
            order.acknowledge()
            self.repository.save(order)
        return order