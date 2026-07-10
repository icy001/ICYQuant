from services.ledger import (
    LedgerEvent,
    LedgerEventType,
    SQLiteEventStore,
)


def create_event():
    return LedgerEvent(
        event_type=
            LedgerEventType.ORDER_FILLED,
        aggregate_id=
            "ACCOUNT-001",
        payload={
            "symbol":
                "NVDA",
            "quantity":
                100,
            "price":
                150.25
        }
    )


def test_sqlite_persistence(
    tmp_path
):
    db = (
        tmp_path /
        "ledger.db"
    )

    store = SQLiteEventStore(
        db
    )

    event = create_event()

    store.append(
        event
    )

    store.close()

    reopened = SQLiteEventStore(
        db
    )

    loaded = reopened.get(
        event.event_id
    )

    assert loaded == event


def test_sqlite_stream(
    tmp_path
):
    db = (
        tmp_path /
        "ledger.db"
    )

    store = SQLiteEventStore(
        db
    )

    store.append(
        create_event()
    )

    events = store.stream(
        "ACCOUNT-001"
    )

    assert len(events) == 1