"""Tests for OrderEventStore — append, read, sequence, hash chain."""

import unittest

from services.oms.events.order_event import OrderEvent
from services.oms.events.order_event_type import OrderEventType
from services.oms.events.order_event_factory import OrderEventFactory
from services.oms.events.order_event_errors import (
    EventSequenceGapError,
    DuplicateEventError,
    EventCollisionError,
    EventConcurrencyConflictError,
)
from services.oms.event_store.order_event_store import InMemoryOrderEventStore
from services.oms.event_store.event_stream import EventStream
from services.oms.event_store.event_store_errors import (
    EventStreamNotFoundError,
    EventStreamClosedError,
)


def _build_stream(store, order_id="ORD-001", count=3):
    """Build a valid event chain in the store."""
    events = []
    prev_hash = ""
    for i in range(1, count + 1):
        evt = OrderEventFactory.created(
            order_id=order_id, sequence=i,
            symbol="NVDA", side="BUY", order_type="MARKET",
            quantity=1000, price=0,
            lineage_id="L-1",
            previous_hash=prev_hash,
        )
        store.append(evt)
        events.append(evt)
        prev_hash = evt.event_hash
    return events


class TestEventStoreAppend(unittest.TestCase):

    def setUp(self):
        self.store = InMemoryOrderEventStore()

    def test_append_creates_stream(self):
        evt = OrderEventFactory.accepted(
            order_id="ORD-001", sequence=1, lineage_id="L-1",
        )
        self.store.append(evt)
        self.assertTrue(self.store.stream_exists("ORD-001"))

    def test_append_multiple_events(self):
        _build_stream(self.store, count=3)
        self.assertEqual(self.store.count("ORD-001"), 3)

    def test_read_returns_events_in_order(self):
        _build_stream(self.store, count=3)
        events = self.store.read("ORD-001")
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0].sequence, 1)
        self.assertEqual(events[2].sequence, 3)


class TestSequenceValidation(unittest.TestCase):

    def setUp(self):
        self.store = InMemoryOrderEventStore()

    def test_sequence_gap_rejected(self):
        evt1 = OrderEventFactory.accepted(
            order_id="ORD-001", sequence=1, lineage_id="L-1",
        )
        self.store.append(evt1)
        # Skip sequence 2, try 3
        evt3 = OrderEventFactory.created(
            order_id="ORD-001", sequence=3,
            symbol="NVDA", side="BUY", order_type="MARKET",
            quantity=1000, lineage_id="L-1",
        )
        with self.assertRaises(EventSequenceGapError):
            self.store.append(evt3)


class TestDuplicateDetection(unittest.TestCase):

    def setUp(self):
        self.store = InMemoryOrderEventStore()
        self.evt = OrderEventFactory.accepted(
            order_id="ORD-001", sequence=1, lineage_id="L-1",
        )
        self.store.append(self.evt)

    def test_duplicate_same_payload_idempotent(self):
        with self.assertRaises(DuplicateEventError) as ctx:
            self.store.append(self.evt)
        self.assertTrue(ctx.exception.idempotent)

    def test_duplicate_different_payload_collision(self):
        evt2 = OrderEventFactory.created(
            order_id="ORD-001", sequence=1,
            symbol="AAPL", side="SELL", order_type="LIMIT",
            quantity=500, price=195, lineage_id="L-1",
        )
        evt2.event_id = self.evt.event_id  # same ID, different content
        evt2.seal()
        with self.assertRaises(EventCollisionError):
            self.store.append(evt2)


class TestOptimisticConcurrency(unittest.TestCase):

    def setUp(self):
        self.store = InMemoryOrderEventStore()

    def test_expected_sequence_match(self):
        evt1 = OrderEventFactory.accepted(
            order_id="ORD-001", sequence=1, lineage_id="L-1",
        )
        self.store.append(evt1, expected_sequence=1)

    def test_expected_sequence_mismatch(self):
        evt1 = OrderEventFactory.accepted(
            order_id="ORD-001", sequence=1, lineage_id="L-1",
        )
        with self.assertRaises(EventConcurrencyConflictError):
            self.store.append(evt1, expected_sequence=5)


class TestTerminalState(unittest.TestCase):

    def test_closed_stream_rejects_append(self):
        store = InMemoryOrderEventStore()
        # Build to FILLED
        prev = ""
        for i, evt_type in enumerate([
            (OrderEventType.ORDER_ACCEPTED, "accepted"),
            (OrderEventType.ORDER_CREATED, "created"),
            (OrderEventType.ORDER_ROUTING_STARTED, "routing_started"),
            (OrderEventType.ORDER_WORKING, "working"),
            (OrderEventType.ORDER_FILLED, "filled"),
        ], start=1):
            factory = getattr(OrderEventFactory, evt_type[1])
            kwargs = dict(order_id="ORD-001", sequence=i,
                          lineage_id="L-1", previous_hash=prev)
            if evt_type[1] == "created":
                kwargs.update(symbol="NVDA", side="BUY",
                              order_type="MARKET", quantity=1000)
            elif evt_type[1] == "filled":
                kwargs.update(fill_quantity=1000, fill_price=850,
                              execution_id="EXEC-1")
            elif evt_type[1] == "routing_started":
                kwargs.update(route="")
            elif evt_type[1] == "working":
                kwargs.update(venue="")
            evt = factory(**kwargs)
            store.append(evt)
            prev = evt.event_hash

        # Stream should be closed
        with self.assertRaises(EventStreamClosedError):
            evt = OrderEventFactory.cancelled(
                order_id="ORD-001", sequence=6,
                lineage_id="L-1", previous_hash=prev,
            )
            store.append(evt)


class TestEventStream(unittest.TestCase):

    def test_stream_read_from(self):
        store = InMemoryOrderEventStore()
        _build_stream(store, count=5)
        stream = store.get_stream("ORD-001")
        from_seq = stream.read_from(3)
        self.assertEqual(len(from_seq), 3)
        self.assertEqual(from_seq[0].sequence, 3)

    def test_stream_read_until(self):
        store = InMemoryOrderEventStore()
        _build_stream(store, count=5)
        stream = store.get_stream("ORD-001")
        until = stream.read_until(2)
        self.assertEqual(len(until), 2)

    def test_stream_read_range(self):
        store = InMemoryOrderEventStore()
        _build_stream(store, count=5)
        stream = store.get_stream("ORD-001")
        rng = stream.read_range(2, 4)
        self.assertEqual(len(rng), 3)

    def test_stream_not_found(self):
        store = InMemoryOrderEventStore()
        with self.assertRaises(EventStreamNotFoundError):
            store.read("NONEXISTENT")

    def test_get_latest(self):
        store = InMemoryOrderEventStore()
        _build_stream(store, count=3)
        latest = store.get_latest("ORD-001")
        self.assertEqual(latest.sequence, 3)


if __name__ == '__main__':
    unittest.main()
