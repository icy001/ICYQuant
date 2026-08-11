"""Tests for event concurrency — optimistic locking and conflicts."""

import unittest

from services.oms.events.order_event_factory import OrderEventFactory
from services.oms.event_store.order_event_store import InMemoryOrderEventStore
from services.oms.event_store.event_stream_writer import EventStreamWriter
from services.oms.events.order_event_errors import (
    EventConcurrencyConflictError,
    DuplicateEventError,
)


class TestOptimisticLocking(unittest.TestCase):

    def setUp(self):
        self.store = InMemoryOrderEventStore()
        self.writer = EventStreamWriter(self.store)

    def test_concurrent_append_conflict(self):
        # Thread A: expects sequence 1, appends successfully
        evt1 = OrderEventFactory.accepted(
            order_id="ORD-001", sequence=1, lineage_id="L-1",
        )
        self.writer.append(evt1, expected_sequence=1)

        # Thread B: also expects sequence 1, should fail
        evt2 = OrderEventFactory.created(
            order_id="ORD-001", sequence=1,
            symbol="NVDA", side="BUY", order_type="MARKET",
            quantity=1000, lineage_id="L-1",
        )
        with self.assertRaises(EventConcurrencyConflictError):
            self.writer.append(evt2, expected_sequence=1)

    def test_auto_sequence_allocation(self):
        evt1 = OrderEventFactory.accepted(
            order_id="ORD-001", sequence=1, lineage_id="L-1",
        )
        self.writer.append(evt1)  # no expected_sequence

        evt2 = OrderEventFactory.created(
            order_id="ORD-001", sequence=0,  # will be overwritten
            symbol="NVDA", side="BUY", order_type="MARKET",
            quantity=1000, lineage_id="L-1",
        )
        self.writer.append(evt2)  # auto-allocates sequence 2
        self.assertEqual(evt2.sequence, 2)


class TestIdempotentAppend(unittest.TestCase):

    def test_idempotent_replay_returns_original(self):
        store = InMemoryOrderEventStore()
        writer = EventStreamWriter(store)

        evt = OrderEventFactory.accepted(
            order_id="ORD-001", sequence=1, lineage_id="L-1",
        )
        writer.append(evt)

        # Replay same event
        result = writer.append_idempotent(evt)
        self.assertEqual(result.event_id, evt.event_id)
        self.assertEqual(store.count("ORD-001"), 1)  # no duplicate


if __name__ == '__main__':
    unittest.main()
