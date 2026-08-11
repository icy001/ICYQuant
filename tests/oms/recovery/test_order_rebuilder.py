"""Tests for OrderRebuilder — event stream replay and recovery."""

import unittest

from services.oms.events.order_event_factory import OrderEventFactory
from services.oms.event_store.order_event_store import InMemoryOrderEventStore
from services.oms.event_store.event_store_snapshot import SnapshotStore
from services.oms.recovery.order_rebuilder import OrderRebuilder
from services.oms.recovery.order_recovery import (
    OrderRecovery, RecoveryStatus,
)
from services.oms.domain.order_status import OrderStatus


def _build_full_order(store, order_id="ORD-001"):
    """Build: ACCEPTED → CREATED → ROUTING → WORKING → PARTIAL → FILLED."""
    prev = ""
    seq = 1

    events_data = [
        ("accepted", {"lineage_id": "L-1", "certificate_id": "C-1"}),
        ("created", {"symbol": "NVDA", "side": "BUY", "order_type": "MARKET",
                      "quantity": 1000, "lineage_id": "L-1", "certificate_id": "C-1"}),
        ("routing_started", {"lineage_id": "L-1"}),
        ("working", {"lineage_id": "L-1"}),
        ("partial_fill", {"fill_quantity": 300, "fill_price": 180,
                          "execution_id": "EXEC-1", "lineage_id": "L-1"}),
        ("filled", {"fill_quantity": 700, "fill_price": 181,
                     "execution_id": "EXEC-2", "lineage_id": "L-1"}),
    ]

    for factory_name, kwargs in events_data:
        factory = getattr(OrderEventFactory, factory_name)
        kwargs["order_id"] = order_id
        kwargs["sequence"] = seq
        kwargs["previous_hash"] = prev
        evt = factory(**kwargs)
        store.append(evt)
        prev = evt.event_hash
        seq += 1

    return store


class TestOrderRebuilder(unittest.TestCase):

    def test_rebuild_full_order(self):
        store = InMemoryOrderEventStore()
        _build_full_order(store)
        rebuilder = OrderRebuilder(store)

        proj = rebuilder.rebuild("ORD-001")
        self.assertEqual(proj.status, OrderStatus.FILLED)
        self.assertEqual(proj.filled_quantity, 1000)
        self.assertEqual(proj.remaining_quantity, 0)
        # VWAP = (300*180 + 700*181) / 1000 = 180.7
        self.assertAlmostEqual(proj.average_price, 180.7, places=1)

    def test_rebuild_from_scratch(self):
        store = InMemoryOrderEventStore()
        _build_full_order(store)
        rebuilder = OrderRebuilder(store)

        proj = rebuilder.rebuild_from_scratch("ORD-001")
        self.assertEqual(proj.status, OrderStatus.FILLED)

    def test_validate_integrity_valid(self):
        store = InMemoryOrderEventStore()
        _build_full_order(store)
        rebuilder = OrderRebuilder(store)
        self.assertTrue(rebuilder.validate_integrity("ORD-001"))

    def test_validate_integrity_nonexistent(self):
        store = InMemoryOrderEventStore()
        rebuilder = OrderRebuilder(store)
        self.assertFalse(rebuilder.validate_integrity("NONEXISTENT"))

    def test_event_count(self):
        store = InMemoryOrderEventStore()
        _build_full_order(store)
        rebuilder = OrderRebuilder(store)
        self.assertEqual(rebuilder.get_event_count("ORD-001"), 6)


class TestOrderRecovery(unittest.TestCase):

    def test_recover_success(self):
        store = InMemoryOrderEventStore()
        _build_full_order(store)
        recovery = OrderRecovery(store)

        result = recovery.recover("ORD-001")
        self.assertTrue(result.is_success)
        self.assertIsNotNone(result.projection)
        self.assertEqual(result.projection.status, OrderStatus.FILLED)

    def test_recover_nonexistent(self):
        store = InMemoryOrderEventStore()
        recovery = OrderRecovery(store)

        result = recovery.recover("NONEXISTENT")
        self.assertEqual(result.status, RecoveryStatus.STREAM_NOT_FOUND)

    def test_recover_all(self):
        store = InMemoryOrderEventStore()
        _build_full_order(store, "ORD-001")
        _build_full_order(store, "ORD-002")
        recovery = OrderRecovery(store)

        results = recovery.recover_all()
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertTrue(r.is_success)

    def test_check_integrity(self):
        store = InMemoryOrderEventStore()
        _build_full_order(store)
        recovery = OrderRecovery(store)
        self.assertTrue(recovery.check_integrity("ORD-001"))


if __name__ == '__main__':
    unittest.main()
