"""Tests for ExecutionRecovery — unknown state recovery."""

import unittest

from services.oms.execution.execution_gateway import InMemoryExecutionGateway
from services.oms.execution.execution_report import ExecutionReport
from services.oms.execution.execution_status import ExecutionStatus
from services.oms.execution.execution_recovery import (
    ExecutionRecovery, RecoveryTrigger,
)


class TestExecutionRecovery(unittest.TestCase):

    def setUp(self):
        self.gateway = InMemoryExecutionGateway()
        self.recovery = ExecutionRecovery(self.gateway, max_attempts=3)

    def test_recover_found_filled(self):
        self.gateway.set_status_query_result("ORD-001", ExecutionReport(
            order_id="ORD-001", status=ExecutionStatus.FILLED,
            executed_quantity=1000, executed_price=850,
        ))
        result = self.recovery.recover_submission("ORD-001")
        self.assertTrue(result.recovered)
        self.assertEqual(result.execution_status, ExecutionStatus.FILLED)

    def test_recover_found_working(self):
        self.gateway.set_status_query_result("ORD-001", ExecutionReport(
            order_id="ORD-001", status=ExecutionStatus.ACCEPTED,
        ))
        result = self.recovery.recover_submission("ORD-001")
        self.assertTrue(result.recovered)
        self.assertEqual(result.execution_status, ExecutionStatus.ACCEPTED)

    def test_recover_not_found_stays_unknown(self):
        # Default query returns UNKNOWN
        result = self.recovery.recover_submission("ORD-001")
        self.assertFalse(result.recovered)
        self.assertEqual(result.execution_status, ExecutionStatus.UNKNOWN)

    def test_recover_cancel(self):
        self.gateway.set_status_query_result("ORD-001", ExecutionReport(
            order_id="ORD-001", status=ExecutionStatus.CANCELLED,
        ))
        result = self.recovery.recover_cancel("ORD-001")
        self.assertTrue(result.recovered)
        self.assertEqual(result.trigger, RecoveryTrigger.CANCEL_TIMEOUT)

    def test_recover_cached(self):
        self.gateway.set_status_query_result("ORD-001", ExecutionReport(
            order_id="ORD-001", status=ExecutionStatus.FILLED,
            executed_quantity=1000, executed_price=850,
        ))
        self.recovery.recover_submission("ORD-001")
        cached = self.recovery.get_cached_result("ORD-001")
        self.assertIsNotNone(cached)
        self.assertTrue(cached.recovered)


if __name__ == '__main__':
    unittest.main()
