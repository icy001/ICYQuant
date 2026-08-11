"""Tests for RepairManager — repair action determination."""

import unittest

from services.oms.reconciliation.reconciliation_result import ReconciliationResult
from services.oms.reconciliation.reconciliation_status import ReconciliationStatus
from services.oms.repair.repair_manager import RepairManager
from services.oms.repair.repair_policy import RepairPolicy
from services.oms.repair.repair_action import RepairActionType


class TestRepairManager(unittest.TestCase):

    def setUp(self):
        self.manager = RepairManager(RepairPolicy.default())

    def _make_result(self, status):
        r = ReconciliationResult(order_id="ORD-001", status=status)
        return r

    def test_consistent_no_repair(self):
        result = self._make_result(ReconciliationStatus.CONSISTENT)
        action = self.manager.evaluate(result)
        self.assertEqual(action.action_type, RepairActionType.NONE)

    def test_oms_stale_auto_repair(self):
        result = self._make_result(ReconciliationStatus.OMS_STALE)
        action = self.manager.evaluate(result)
        self.assertEqual(action.action_type, RepairActionType.REPLAY_EXECUTION)

    def test_critical_freezes_order(self):
        result = self._make_result(ReconciliationStatus.CRITICAL)
        action = self.manager.evaluate(result)
        self.assertEqual(action.action_type, RepairActionType.FREEZE_ORDER)
        self.assertTrue(self.manager.is_frozen("ORD-001"))

    def test_state_mismatch_escalates(self):
        result = self._make_result(ReconciliationStatus.STATE_MISMATCH)
        action = self.manager.evaluate(result)
        self.assertEqual(action.action_type, RepairActionType.ESCALATE)

    def test_quantity_mismatch_escalates(self):
        result = self._make_result(ReconciliationStatus.QUANTITY_MISMATCH)
        action = self.manager.evaluate(result)
        self.assertEqual(action.action_type, RepairActionType.ESCALATE)

    def test_unfreeze(self):
        result = self._make_result(ReconciliationStatus.CRITICAL)
        self.manager.evaluate(result)
        self.assertTrue(self.manager.is_frozen("ORD-001"))
        self.manager.unfreeze("ORD-001")
        self.assertFalse(self.manager.is_frozen("ORD-001"))

    def test_conservative_policy_no_auto_repair(self):
        manager = RepairManager(RepairPolicy.conservative())
        result = self._make_result(ReconciliationStatus.OMS_STALE)
        action = manager.evaluate(result)
        self.assertEqual(action.action_type, RepairActionType.ESCALATE)


if __name__ == '__main__':
    unittest.main()
