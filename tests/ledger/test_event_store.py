import pytest

from services.ledger.event import LedgerEvent
from services.ledger.event_type import LedgerEventType
from services.ledger.store import InMemoryEventStore, SQLiteEventStore


class TestEventStore:

    def test_append_event(self):
        store = InMemoryEventStore()
        event = LedgerEvent(event_type=LedgerEventType.CASH_DEPOSITED, payload={"amount": 100000.0})

        store.append(event)

        events = store.all_events()
        assert len(events) == 1
        assert events[0].event_type == LedgerEventType.CASH_DEPOSITED

    def test_load_stream(self):
        store = InMemoryEventStore()
        event1 = LedgerEvent(event_type=LedgerEventType.CASH_DEPOSITED, payload={"amount": 100000.0}, aggregate_id="account1")
        event2 = LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"symbol": "NVDA"}, aggregate_id="account2")

        store.append(event1)
        store.append(event2)

        events = store.stream("account1")
        assert len(events) == 1
        assert events[0].aggregate_id == "account1"

    def test_replay_sorted(self):
        store = InMemoryEventStore()
        from datetime import datetime, timezone, timedelta
        t1 = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2024, 1, 1, 10, 0, 1, tzinfo=timezone.utc)
        
        event2 = LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"symbol": "NVDA"}, timestamp=t2)
        event1 = LedgerEvent(event_type=LedgerEventType.CASH_DEPOSITED, payload={"amount": 100000.0}, timestamp=t1)

        store.append(event2)
        store.append(event1)

        events = store.all_events()
        assert len(events) == 2
        assert events[0].event_type == LedgerEventType.CASH_DEPOSITED
        assert events[1].event_type == LedgerEventType.ORDER_FILLED

    def test_get_by_id(self):
        store = InMemoryEventStore()
        event = LedgerEvent(event_type=LedgerEventType.CASH_DEPOSITED, payload={"amount": 100000.0})

        store.append(event)

        retrieved = store.get(event.event_id)
        assert retrieved is not None
        assert retrieved.event_id == event.event_id

    def test_append_many(self):
        store = InMemoryEventStore()
        events = [
            LedgerEvent(event_type=LedgerEventType.CASH_DEPOSITED, payload={"amount": 100000.0}),
            LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"symbol": "NVDA"}),
        ]

        store.append_many(events)

        assert len(store.all_events()) == 2

    def test_sqlite_append_and_replay(self):
        store = SQLiteEventStore(":memory:")
        event = LedgerEvent(event_type=LedgerEventType.CASH_DEPOSITED, payload={"amount": 100000.0}, aggregate_id="test_user")

        store.append(event)

        events = store.all_events()
        assert len(events) == 1
        assert events[0].event_type == LedgerEventType.CASH_DEPOSITED

    def test_sqlite_stream(self):
        store = SQLiteEventStore(":memory:")
        event1 = LedgerEvent(event_type=LedgerEventType.CASH_DEPOSITED, payload={"amount": 100000.0}, aggregate_id="user1")
        event2 = LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"symbol": "NVDA"}, aggregate_id="user1")

        store.append(event1)
        store.append(event2)

        stream = store.stream("user1")
        assert len(stream) == 2