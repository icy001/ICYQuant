import pytest

from services.oms.models import Order
from services.oms.service import OrderService
from services.oms.state import OrderStatus


class TestOMS:
    def test_create_order(self):
        service = OrderService()

        order = service.create_order(
            symbol="NVDA",
            side="BUY",
            quantity=100,
            price=480.0,
        )

        assert order.order_id is not None
        assert order.symbol == "NVDA"
        assert order.side == "BUY"
        assert order.quantity == 100
        assert order.price == 480.0

    def test_order_state_transitions(self):
        service = OrderService()

        order = service.create_order(
            symbol="NVDA",
            side="BUY",
            quantity=100,
        )

        assert order.status == OrderStatus.NEW

        order = service.submit_order(order.order_id)
        assert order.status == OrderStatus.SUBMITTED

        order = service.accept_order(order.order_id)
        assert order.status == OrderStatus.ACCEPTED

        order = service.fill_order(order.order_id)
        assert order.status == OrderStatus.FILLED