"""
Tests: Approval Gate
Commit 21 Part 1.1
"""

import sys
import os
import unittest
import types
import importlib.util
import time

_ws = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if "services" not in sys.modules:
    _svc = types.ModuleType("services")
    _svc.__path__ = [os.path.join(_ws, "services")]
    sys.modules["services"] = _svc

_svc_dir = os.path.join(_ws, "services")
_int_dir = os.path.join(_svc_dir, "integration")

if "services.integration" not in sys.modules:
    _mod = types.ModuleType("services.integration")
    _mod.__path__ = [_int_dir]
    sys.modules["services.integration"] = _mod

for _name in [
    "control_state", "control_context", "control_result", "control_gate",
    "approval_gate",
]:
    _fp = os.path.join(_int_dir, f"{_name}.py")
    _spec = importlib.util.spec_from_file_location(
        f"services.integration.{_name}", _fp
    )
    _m = importlib.util.module_from_spec(_spec)
    sys.modules[f"services.integration.{_name}"] = _m
    _spec.loader.exec_module(_m)

from services.integration.control_context import TradingControlContext
from services.integration.control_result import GateStatus
from services.integration.approval_gate import ApprovalGate


class TestApprovalGate(unittest.TestCase):
    """Approval gate validation."""

    def setUp(self):
        self.gate = ApprovalGate()
        self.ctx = TradingControlContext(flow_id="FLOW-TEST")

    def test_approved_passes(self):
        self.gate.approval_status = "APPROVED"
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.PASS)

    def test_pending_rejects(self):
        self.gate.approval_status = "PENDING"
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)
        self.assertIn("pending", result.reason.lower())

    def test_rejected_rejects(self):
        self.gate.approval_status = "REJECTED"
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)

    def test_expired_returns_expired(self):
        self.gate.approval_status = "EXPIRED"
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.EXPIRED)

    def test_consumed_returns_reject(self):
        self.gate.approval_status = "APPROVED"
        self.gate.consumed = True
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)
        self.assertIn("consumed", result.reason.lower())

    def test_expired_by_time(self):
        self.gate.approval_status = "APPROVED"
        self.gate.valid_until = time.time() - 60  # 1 minute ago
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.EXPIRED)

    def test_amount_exceeded_rejects(self):
        self.gate.approval_status = "APPROVED"
        self.gate.approved_amount = 10000
        self.ctx.with_approval_context({"requested_amount": 15000})
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)
        self.assertIn("exceeds", result.reason)

    def test_amount_within_limit_passes(self):
        self.gate.approval_status = "APPROVED"
        self.gate.approved_amount = 20000
        self.ctx.with_approval_context({"requested_amount": 10000})
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.PASS)

    def test_scope_mismatch_rejects(self):
        self.gate.approval_status = "APPROVED"
        self.gate.approved_action = "CAPITAL_ALLOCATION"
        self.ctx.decision_type = "LEVERAGE_CHANGE"
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)

    def test_policy_version_mismatch_rejects(self):
        self.gate.approval_status = "APPROVED"
        self.gate.approval_policy_version = "v1"
        self.ctx.policy_version = "v2"
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)
        self.assertIn("policy", result.reason.lower())

    def test_approved_from_context(self):
        self.ctx.with_approval_context({"status": "APPROVED"})
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.PASS)

    def test_unknown_approval_fails_closed(self):
        self.ctx.with_approval_context({"state": "UNKNOWN"})
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.BLOCK)

    def test_invalid_status_rejects(self):
        self.gate.approval_status = "INVALID_STATE"
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)

    def test_context_overrides_gate_state(self):
        # Context APPROVED should override gate PENDING
        self.gate.approval_status = "PENDING"
        self.ctx.with_approval_context({"status": "APPROVED"})
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.PASS)


if __name__ == "__main__":
    unittest.main()
