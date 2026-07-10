import pytest

from services.ledger.event import LedgerEvent, LedgerEventType
from services.ledger.store import InMemoryEventStore


class TestEventStore:

    def test_append_event(self):
        store = InMemoryEventStore()
        event = LedgerEvent(event_type=LedgerEventType.DEPOSIT, payload={"amount": 100000.0})

        store.append(event)

        events = store.replay()
        assert len(events) == 1
        assert events[0].event_type == LedgerEventType.DEPOSIT

    def test_load_stream(self):
        store = InMemoryEventStore()
        event1 = LedgerEvent(event_type=LedgerEventType.DEPOSIT, payload={"amount": 100000.0}, stream_id="account1")
        event2 = LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"symbol": "NVDA"}, stream_id="account2")

        store.append(event1)
        store.append(event2)

        events = store.load("account1")
        assert len(events) == 1
        assert events[0].stream_id == "account1"

    def test_replay_sorted(self):
        store = InMemoryEventStore()
        from datetime import datetime, timedelta
        t1 = datetime(2024, 1, 1, 10, 0, 0)
        t2 = datetime(2024, 1, 1, 10, 0, 1)
        
        event2 = LedgerEvent(event_type=LedgerEventType.ORDER_FILLED, payload={"symbol": "NVDA"}, timestamp=t2)
        event1 = LedgerEvent(event_type=LedgerEventType.DEPOSIT, payload={"amount": 100000.0}, timestamp=t1)

        store.append(event2)
        store.append(event1)

        events = store.replay()
        assert len(events) == 2
        assert events[0].event_type == LedgerEventType.DEPOSIT
        assert events[1].event_type == LedgerEventType.ORDER_FILLED