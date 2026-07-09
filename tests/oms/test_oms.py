import pytest

from services.contracts.dto import OrderDTO
from services.eventbus.publisher import EventPublisher
from services.oms.service.oms import OMS


class TestOMS:
    def test_create_order(self):
        bus = EventPublisher()
        oms = OMS(bus)
        order = OrderDTO(order_id="test-order", user_id="u1", symbol="AAPL", side="BUY", quantity=10.0, status="NEW")
        event = oms.create_order(order)
        assert event.event_type.value == "ORDER_CREATED"
        assert event.order_id == "test-order"
