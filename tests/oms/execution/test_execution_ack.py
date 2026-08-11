"""Tests for ExecutionAckHandler — ACK processing and duplicate detection."""

import unittest

from services.oms.execution.execution_response import ExecutionAck
from services.oms.execution.execution_status import ExecutionStatus
from services.oms.execution.execution_ack_handler import ExecutionAckHandler
from services.oms.execution.execution_error import (
    RequestIdReuseConflictError,
    ExecutionError,
)


class TestAckHandler(unittest.TestCase):

    def setUp(self):
        self.handler = ExecutionAckHandler()

    def test_process_accepted_ack(self):
        ack = ExecutionAck.accepted("REQ-001", "ORD-001")
        result = self.handler.handle(ack)
        self.assertEqual(result["status"], "PROCESSED")
        self.assertTrue(result["accepted"])

    def test_process_rejected_ack(self):
        ack = ExecutionAck.rejected("REQ-001", "ORD-001", "VENUE_REJECTED")
        result = self.handler.handle(ack)
        self.assertEqual(result["status"], "PROCESSED")
        self.assertFalse(result["accepted"])

    def test_duplicate_ack_idempotent(self):
        ack = ExecutionAck.accepted("REQ-001", "ORD-001")
        self.handler.handle(ack)
        result = self.handler.handle(ack)
        self.assertEqual(result["status"], "IDEMPOTENT_REPLAY")

    def test_duplicate_ack_conflict(self):
        ack1 = ExecutionAck.accepted("REQ-001", "ORD-001")
        self.handler.handle(ack1)
        ack2 = ExecutionAck.rejected("REQ-001", "ORD-001")
        with self.assertRaises(RequestIdReuseConflictError):
            self.handler.handle(ack2)

    def test_missing_request_id(self):
        ack = ExecutionAck(request_id="", order_id="ORD-001")
        with self.assertRaises(ExecutionError):
            self.handler.handle(ack)

    def test_is_processed(self):
        ack = ExecutionAck.accepted("REQ-001", "ORD-001")
        self.handler.handle(ack)
        self.assertTrue(self.handler.is_processed("REQ-001"))


if __name__ == '__main__':
    unittest.main()
