from services.ledger import (
    LedgerEvent,
    LedgerEventType,
    MemoryEventStore,
    LedgerRepository,
)


def test_repository_append():
    store = MemoryEventStore()

    repository = LedgerRepository(
        store
    )

    event = LedgerEvent(
        event_type=
            LedgerEventType.CASH_DEPOSITED,
        aggregate_id=
            "ACCOUNT-001",
        payload={
            "amount":
                100000
        }
    )

    repository.append(
        event
    )

    result = repository.get(
        event.event_id
    )

    assert result == event


def test_replay_source():
    repository = LedgerRepository(
        MemoryEventStore()
    )

    event = LedgerEvent(
        event_type=
            LedgerEventType.ORDER_FILLED,
        aggregate_id=
            "PORTFOLIO-001",
        payload={
            "symbol":
                "NVDA"
        }
    )

    repository.append(
        event
    )

    replay_events = list(
        repository.replay_source()
    )

    assert len(
        replay_events
    ) == 1