"""Tests for mismatch detection."""

import unittest

from services.oms.reconciliation.mismatch import (
    Mismatch, MismatchType,
)
from services.oms.reconciliation.mismatch_severity import MismatchSeverity


class TestMismatchCreation(unittest.TestCase):

    def test_status_mismatch(self):
        m = Mismatch.status_mismatch("ORD-001", "WORKING", "FILLED")
        self.assertEqual(m.mismatch_type, MismatchType.STATUS_MISMATCH)
        self.assertEqual(m.oms_value, "WORKING")
        self.assertEqual(m.execution_value, "FILLED")

    def test_status_mismatch_critical(self):
        m = Mismatch.status_mismatch("ORD-001", "CANCELLED", "FILLED")
        self.assertEqual(m.severity, MismatchSeverity.CRITICAL)

    def test_quantity_mismatch(self):
        m = Mismatch.quantity_mismatch("ORD-001", 500, 800)
        self.assertEqual(m.mismatch_type, MismatchType.QUANTITY_MISMATCH)
        self.assertEqual(m.severity, MismatchSeverity.ERROR)

    def test_missing_execution(self):
        m = Mismatch.missing_execution("ORD-001", "EXEC-003")
        self.assertEqual(m.mismatch_type, MismatchType.MISSING_EXECUTION)
        self.assertEqual(m.execution_value, "EXEC-003")

    def test_to_dict(self):
        m = Mismatch.status_mismatch("ORD-001", "WORKING", "FILLED")
        d = m.to_dict()
        self.assertEqual(d["order_id"], "ORD-001")
        self.assertEqual(d["mismatch_type"], "STATUS_MISMATCH")


class TestMismatchSeverity(unittest.TestCase):

    def test_is_critical(self):
        self.assertTrue(MismatchSeverity.CRITICAL.is_critical)
        self.assertFalse(MismatchSeverity.WARNING.is_critical)

    def test_is_error(self):
        self.assertTrue(MismatchSeverity.ERROR.is_error)
        self.assertTrue(MismatchSeverity.CRITICAL.is_error)
        self.assertFalse(MismatchSeverity.WARNING.is_error)


if __name__ == '__main__':
    unittest.main()
