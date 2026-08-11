"""Tests for ExecutionReconciler — execution record reconciliation."""

import unittest

from services.oms.reconciliation.execution_reconciler import ExecutionReconciler
from services.oms.reconciliation.reconciliation_status import ReconciliationStatus


class TestExecutionReconciler(unittest.TestCase):

    def setUp(self):
        self.reconciler = ExecutionReconciler()

    def test_consistent(self):
        oms_execs = [{"execution_id": "EXEC-1", "fill_quantity": 300, "fill_price": 180}]
        exec_execs = [{"execution_id": "EXEC-1", "fill_quantity": 300, "fill_price": 180}]
        result = self.reconciler.reconcile("ORD-001", oms_execs, exec_execs)
        self.assertTrue(result.is_consistent)

    def test_missing_execution_in_oms(self):
        oms_execs = [{"execution_id": "EXEC-1", "fill_quantity": 300, "fill_price": 180}]
        exec_execs = [
            {"execution_id": "EXEC-1", "fill_quantity": 300, "fill_price": 180},
            {"execution_id": "EXEC-2", "fill_quantity": 200, "fill_price": 181},
        ]
        result = self.reconciler.reconcile("ORD-001", oms_execs, exec_execs)
        self.assertTrue(result.has_mismatches)

    def test_quantity_mismatch_in_execution(self):
        oms_execs = [{"execution_id": "EXEC-1", "fill_quantity": 300, "fill_price": 180}]
        exec_execs = [{"execution_id": "EXEC-1", "fill_quantity": 500, "fill_price": 180}]
        result = self.reconciler.reconcile("ORD-001", oms_execs, exec_execs)
        self.assertTrue(result.has_mismatches)


if __name__ == '__main__':
    unittest.main()
