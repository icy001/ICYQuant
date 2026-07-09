import pytest

from services.contracts.events import Event, EventType
from services.eventbus.publisher import EventPublisher
from services.execution.service.execution_engine import ExecutionEngine


class TestExecutionEngine:
    def test_on_approved(self):
        bus = EventPublisher()
        engine = ExecutionEngine(bus)

        event = Event(
            event_id="test-event",
            event_type=EventType.ORDER_APPROVED,
            order_id="test-order",
            timestamp=__import__("datetime").datetime.utcnow(),
            payload={"symbol": "AAPL", "side": "BUY", "quantity": 10.0},
        )
        bus.publish(event)
