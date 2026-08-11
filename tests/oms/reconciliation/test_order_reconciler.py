"""Tests for OrderReconciler — OMS vs Execution state reconciliation."""

import unittest

from services.oms.projection.order_projection import OrderProjection
from services.oms.domain.order_status import OrderStatus
from services.oms.reconciliation.order_reconciler import OrderReconciler
from services.oms.reconciliation.reconciliation_status import ReconciliationStatus


def _make_projection(order_id="ORD-001", status=OrderStatus.WORKING,
                     filled=0, original=1000):
    return OrderProjection(
        order_id=order_id, status=status,
        original_quantity=original,
        filled_quantity=filled,
        remaining_quantity=original - filled,
    )


class TestOrderReconciler(unittest.TestCase):

    def setUp(self):
        self.reconciler = OrderReconciler()

    def test_consistent_working(self):
        proj = _make_projection(status=OrderStatus.WORKING)
        exec_state = {"status": "ACCEPTED", "filled_quantity": 0}
        result = self.reconciler.reconcile(proj, exec_state)
        self.assertTrue(result.is_consistent)

    def test_consistent_filled(self):
        proj = _make_projection(status=OrderStatus.FILLED, filled=1000)
        exec_state = {"status": "FILLED", "filled_quantity": 1000}
        result = self.reconciler.reconcile(proj, exec_state)
        self.assertTrue(result.is_consistent)

    def test_oms_stale(self):
        proj = _make_projection(status=OrderStatus.WORKING, filled=300)
        exec_state = {"status": "PARTIALLY_FILLED", "filled_quantity": 500}
        result = self.reconciler.reconcile(proj, exec_state)
        self.assertEqual(result.status, ReconciliationStatus.OMS_STALE)

    def test_quantity_mismatch(self):
        proj = _make_projection(status=OrderStatus.FILLED, filled=1000)
        exec_state = {"status": "FILLED", "filled_quantity": 800}
        result = self.reconciler.reconcile(proj, exec_state)
        self.assertTrue(result.has_mismatches)

    def test_critical_state_mismatch(self):
        proj = _make_projection(status=OrderStatus.CANCELLED)
        exec_state = {"status": "FILLED", "filled_quantity": 1000}
        result = self.reconciler.reconcile(proj, exec_state)
        self.assertEqual(result.status, ReconciliationStatus.STATE_MISMATCH)

    def test_unknown_execution_state(self):
        proj = _make_projection(status=OrderStatus.WORKING)
        exec_state = {"status": "UNKNOWN"}
        result = self.reconciler.reconcile(proj, exec_state)
        self.assertEqual(result.status, ReconciliationStatus.UNKNOWN)


if __name__ == '__main__':
    unittest.main()
