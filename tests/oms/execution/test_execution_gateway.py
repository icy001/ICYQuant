"""Tests for ExecutionGateway — submit, cancel, query."""

import unittest

from services.oms.execution.execution_gateway import InMemoryExecutionGateway
from services.oms.execution.execution_request import ExecutionRequest, CancelRequest
from services.oms.execution.execution_response import ExecutionAck
from services.oms.execution.execution_status import ExecutionStatus
from services.oms.execution.execution_error import (
    ExecutionTimeoutError,
    RequestIdReuseConflictError,
)


def _make_request(order_id="ORD-001", request_id="EXREQ-001", **kwargs):
    defaults = dict(
        request_id=request_id,
        order_id=order_id,
        symbol="NVDA", side="BUY", quantity=1000,
        order_type="MARKET",
        lineage_id="L-1", correlation_id="F-1",
    )
    defaults.update(kwargs)
    return ExecutionRequest(**defaults)


class TestExecutionGateway(unittest.TestCase):

    def setUp(self):
        self.gateway = InMemoryExecutionGateway()

    def test_submit_success(self):
        req = _make_request()
        ack = self.gateway.submit(req)
        self.assertEqual(ack.status, ExecutionStatus.ACCEPTED)
        self.assertTrue(ack.venue_order_id)

    def test_submit_idempotent_replay(self):
        req = _make_request()
        ack1 = self.gateway.submit(req)
        ack2 = self.gateway.submit(req)
        self.assertEqual(ack1.request_id, ack2.request_id)

    def test_submit_request_hash_conflict(self):
        req1 = _make_request(request_id="EXREQ-001", quantity=1000)
        self.gateway.submit(req1)
        # Same request_id, different quantity
        req2 = _make_request(request_id="EXREQ-001", quantity=2000)
        with self.assertRaises(RequestIdReuseConflictError):
            self.gateway.submit(req2)

    def test_submit_timeout(self):
        self.gateway.configure_submit_timeout(True)
        with self.assertRaises(ExecutionTimeoutError):
            self.gateway.submit(_make_request())

    def test_cancel_success(self):
        req = CancelRequest(order_id="ORD-001", request_id="EXREQ-001")
        ack = self.gateway.cancel(req)
        self.assertEqual(ack.status, ExecutionStatus.CANCELLED)

    def test_cancel_timeout(self):
        self.gateway.configure_cancel_timeout(True)
        req = CancelRequest(order_id="ORD-001")
        with self.assertRaises(ExecutionTimeoutError):
            self.gateway.cancel(req)

    def test_query_status_unknown(self):
        report = self.gateway.query_status("ORD-001")
        self.assertEqual(report.status, ExecutionStatus.UNKNOWN)

    def test_query_status_configured(self):
        from services.oms.execution.execution_report import ExecutionReport
        self.gateway.set_status_query_result("ORD-001", ExecutionReport(
            order_id="ORD-001", status=ExecutionStatus.FILLED,
            executed_quantity=1000, executed_price=850,
        ))
        report = self.gateway.query_status("ORD-001")
        self.assertEqual(report.status, ExecutionStatus.FILLED)


if __name__ == '__main__':
    unittest.main()
