from services.eventbus import *
from .mock_handler import MockHandler


def test_event_bus():
    bus = EventBus()

    subscriber = EventSubscriber()

    handler = MockHandler()

    subscriber.register(handler)

    bus.subscribe(subscriber)

    event = Event(
        "EV001",
        EventType.ORDER_CREATED,
        {
            "order_id": "ORD001"
        }
    )

    bus.publish(event)

    assert handler.received.event_id == "EV001"