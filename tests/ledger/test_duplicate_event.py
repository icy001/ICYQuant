import pytest

from services.ledger import (
    LedgerEvent,
    LedgerEventType,
    MemoryEventStore,
    DuplicateEventError,
)


def test_duplicate_event_rejected():
    store = MemoryEventStore()

    event = LedgerEvent(
        event_type=
            LedgerEventType.ORDER_FILLED,
        payload={
            "symbol":
                "NVDA"
        }
    )

    store.append(
        event
    )

    with pytest.raises(
        DuplicateEventError
    ):
        store.append(
            event
        )