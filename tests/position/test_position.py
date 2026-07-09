import pytest

from services.contracts.events import Event, EventType
from services.eventbus.publisher import EventPublisher
from services.position.service.position_service import PositionService


class TestPositionService:
    def test_on_trade_buy(self):
        bus = EventPublisher()
        service = PositionService(bus)

        event = Event(
            event_id="test-event",
            event_type=EventType.TRADE_EXECUTED,
            order_id="test-order",
            timestamp=__import__("datetime").datetime.utcnow(),
            payload={"symbol": "AAPL", "side": "BUY", "qty": 10.0},
        )
        bus.publish(event)
        assert service.positions.get("AAPL") == 10.0

    def test_on_trade_sell(self):
        bus = EventPublisher()
        service = PositionService(bus)

        event = Event(
            event_id="test-event",
            event_type=EventType.TRADE_EXECUTED,
            order_id="test-order",
            timestamp=__import__("datetime").datetime.utcnow(),
            payload={"symbol": "AAPL", "side": "SELL", "qty": 5.0},
        )
        bus.publish(event)
        assert service.positions.get("AAPL") == -5.0
