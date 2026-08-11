"""Tests for OrderProjector — projection building and snapshots."""

import unittest

from services.oms.events.order_event_factory import OrderEventFactory
from services.oms.event_store.order_event_store import InMemoryOrderEventStore
from services.oms.event_store.event_store_snapshot import (
    EventStoreSnapshot, SnapshotStore,
)
from services.oms.projection.order_projector import OrderProjector
from services.oms.projection.order_projection import OrderProjection
from services.oms.domain.order_status import OrderStatus


def _build_order(store, order_id="ORD-001"):
    """Build: ACCEPTED → CREATED → ROUTING → WORKING."""
    prev = ""
    seq = 1

    e1 = OrderEventFactory.accepted(
        order_id=order_id, sequence=seq,
        lineage_id="L-1", certificate_id="C-1",
        previous_hash=prev,
    )
    store.append(e1)
    prev = e1.event_hash
    seq += 1

    e2 = OrderEventFactory.created(
        order_id=order_id, sequence=seq,
        symbol="NVDA", side="BUY", order_type="MARKET",
        quantity=1000, lineage_id="L-1", certificate_id="C-1",
        previous_hash=prev,
    )
    store.append(e2)
    prev = e2.event_hash
    seq += 1

    e3 = OrderEventFactory.routing_started(
        order_id=order_id, sequence=seq,
        lineage_id="L-1", previous_hash=prev,
    )
    store.append(e3)
    prev = e3.event_hash
    seq += 1

    e4 = OrderEventFactory.working(
        order_id=order_id, sequence=seq,
        lineage_id="L-1", previous_hash=prev,
    )
    store.append(e4)
    return store


class TestProjectorRebuild(unittest.TestCase):

    def test_rebuild_from_events(self):
        store = InMemoryOrderEventStore()
        _build_order(store)
        projector = OrderProjector(store, use_snapshots=False)

        proj = projector.rebuild("ORD-001")
        self.assertEqual(proj.status, OrderStatus.WORKING)
        self.assertEqual(proj.original_quantity, 1000)
        self.assertEqual(proj.last_event_sequence, 4)

    def test_rebuild_nonexistent(self):
        store = InMemoryOrderEventStore()
        projector = OrderProjector(store)
        proj = projector.rebuild("NONEXISTENT")
        self.assertEqual(proj.status, OrderStatus.RECEIVED)

    def test_apply_event_live(self):
        store = InMemoryOrderEventStore()
        projector = OrderProjector(store, use_snapshots=False)

        e1 = OrderEventFactory.accepted(
            order_id="ORD-001", sequence=1,
            lineage_id="L-1", certificate_id="C-1",
        )
        store.append(e1)
        proj = projector.apply_event(e1)
        self.assertEqual(proj.status, OrderStatus.ACCEPTED)


class TestProjectorLag(unittest.TestCase):

    def test_lag_zero_when_current(self):
        store = InMemoryOrderEventStore()
        _build_order(store)
        projector = OrderProjector(store, use_snapshots=False)
        projector.rebuild("ORD-001")
        self.assertEqual(projector.get_lag("ORD-001"), 0)

    def test_lag_positive_when_behind(self):
        store = InMemoryOrderEventStore()
        _build_order(store)
        projector = OrderProjector(store, use_snapshots=False)
        proj = projector.rebuild("ORD-001")

        # Add another event without updating projection
        e5 = OrderEventFactory.partial_fill(
            order_id="ORD-001", sequence=5,
            fill_quantity=300, fill_price=180,
            execution_id="EXEC-1", lineage_id="L-1",
            previous_hash=proj.last_event_hash,
        )
        store.append(e5)
        self.assertEqual(projector.get_lag("ORD-001"), 1)
        self.assertTrue(projector.is_stale("ORD-001"))


class TestSnapshot(unittest.TestCase):

    def test_create_and_use_snapshot(self):
        store = InMemoryOrderEventStore()
        _build_order(store)
        projector = OrderProjector(store, use_snapshots=True)

        proj = projector.rebuild("ORD-001")
        snapshot = projector.create_snapshot("ORD-001")
        self.assertIsNotNone(snapshot)
        self.assertTrue(snapshot.verify())

        # Rebuild should use snapshot
        proj2 = projector.rebuild("ORD-001")
        self.assertEqual(proj2.status, OrderStatus.WORKING)

    def test_snapshot_validation(self):
        snap = EventStoreSnapshot.create(
            order_id="ORD-001", sequence=5,
            status=OrderStatus.WORKING,
            filled_quantity=300, remaining_quantity=700,
            original_quantity=1000, average_price=180,
            last_event_hash="abc123",
        )
        self.assertTrue(snap.verify())

        # Tamper
        snap.filled_quantity = 999
        self.assertFalse(snap.verify())


if __name__ == '__main__':
    unittest.main()
