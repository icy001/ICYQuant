from services.event_store import *


def test_event_replay():
    store = EventStore()
    service = EventSourcingService(store)

    event = DomainEvent(
        "EV001",
        "ORDER001",
        "ORDER_CREATED",
        {
            "status": "CREATED"
        }
    )

    service.publish(event)

    result = service.replay()

    assert len(result) == 1
