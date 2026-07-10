from services.ledger import (
    LedgerEvent,
    LedgerEventType,
)


def test_event_serialization():
    event = LedgerEvent(
        event_type=
            LedgerEventType.ORDER_FILLED,
        aggregate_id=
            "PORTFOLIO-001",
        payload={
            "symbol":
                "NVDA",
            "quantity":
                100,
            "price":
                150.5,
        },
    )

    data = event.to_dict()

    restored = LedgerEvent.from_dict(
        data
    )

    assert (
        restored.event_id
        ==
        event.event_id
    )

    assert (
        restored.event_type
        ==
        event.event_type
    )

    assert (
        restored.payload
        ==
        event.payload
    )