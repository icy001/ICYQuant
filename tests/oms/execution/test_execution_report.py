"""Tests for ExecutionReportHandler — fill, duplicate, conflict handling."""

import unittest

from services.oms.execution.execution_report import ExecutionReport
from services.oms.execution.execution_status import ExecutionStatus
from services.oms.execution.execution_report_handler import ExecutionReportHandler
from services.oms.execution.execution_error import (
    ExecutionError,
    ExecutionQuantityExceededError,
)


class TestReportHandler(unittest.TestCase):

    def setUp(self):
        self.handler = ExecutionReportHandler()

    def test_partial_fill(self):
        report = ExecutionReport.partial_fill(
            "EXEC-001", "ORD-001",
            executed_quantity=300, executed_price=180,
            remaining_quantity=700,
        )
        result = self.handler.handle(report, remaining_quantity=1000)
        self.assertEqual(result["status"], "PROCESSED")
        self.assertEqual(result["action"], "APPLY_PARTIAL_FILL")

    def test_full_fill(self):
        report = ExecutionReport.full_fill(
            "EXEC-001", "ORD-001",
            executed_quantity=1000, executed_price=850,
        )
        result = self.handler.handle(report, remaining_quantity=1000)
        self.assertEqual(result["action"], "APPLY_FULL_FILL")

    def test_duplicate_idempotent(self):
        report = ExecutionReport.partial_fill(
            "EXEC-001", "ORD-001", 300, 180,
        )
        self.handler.handle(report, remaining_quantity=1000)
        result = self.handler.handle(report, remaining_quantity=700)
        self.assertEqual(result["status"], "IDEMPOTENT_REPLAY")

    def test_conflicting_execution_id(self):
        r1 = ExecutionReport.partial_fill(
            "EXEC-001", "ORD-001", 300, 180,
        )
        self.handler.handle(r1, remaining_quantity=1000)

        r2 = ExecutionReport.partial_fill(
            "EXEC-001", "ORD-001", 500, 181,
        )
        with self.assertRaises(ExecutionError) as ctx:
            self.handler.handle(r2, remaining_quantity=700)
        self.assertEqual(ctx.exception.code, "EXECUTION_ID_CONFLICT")

    def test_quantity_exceeded(self):
        report = ExecutionReport.partial_fill(
            "EXEC-001", "ORD-001", 800, 180,
        )
        with self.assertRaises(ExecutionQuantityExceededError):
            self.handler.handle(report, remaining_quantity=500)

    def test_rejected_report(self):
        report = ExecutionReport.rejected(
            "ORD-001", "VENUE_REJECTED", "Invalid size",
        )
        result = self.handler.handle(report)
        self.assertEqual(result["action"], "REJECT_ORDER")

    def test_cancelled_report(self):
        report = ExecutionReport.cancelled("ORD-001", cancelled_quantity=1000)
        result = self.handler.handle(report)
        self.assertEqual(result["action"], "CONFIRM_CANCEL")


if __name__ == '__main__':
    unittest.main()
