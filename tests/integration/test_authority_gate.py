"""
Tests: Authority Gate
Commit 21 Part 1.1
"""

import sys
import os
import unittest
import types
import importlib.util

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
    "authority_gate",
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
from services.integration.authority_gate import AuthorityGate


class TestAuthorityGate(unittest.TestCase):
    """Authority gate validation."""

    def setUp(self):
        self.gate = AuthorityGate()
        self.ctx = TradingControlContext(flow_id="FLOW-TEST")

    def test_authorized_passes(self):
        self.gate.has_authority = True
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.PASS)

    def test_no_authority_rejects(self):
        self.gate.has_authority = False
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)
        self.assertIn("No authority", result.reason)

    def test_revoked_rejects(self):
        self.gate.has_authority = True
        self.gate.revoked = True
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)
        self.assertIn("revoked", result.reason.lower())

    def test_expired_returns_expired(self):
        self.gate.has_authority = True
        self.gate.expired = True
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.EXPIRED)

    def test_amount_exceeds_limit_rejects(self):
        self.gate.has_authority = True
        self.gate.max_amount = 10000
        self.ctx.with_authority_context({"requested_amount": 15000})
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)
        self.assertIn("exceeds", result.reason)

    def test_amount_within_limit_passes(self):
        self.gate.has_authority = True
        self.gate.max_amount = 20000
        self.ctx.with_authority_context({"requested_amount": 10000})
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.PASS)

    def test_delegation_limit_caps_amount(self):
        self.gate.has_authority = True
        self.gate.max_amount = 100000
        self.gate.delegation_active = True
        self.gate.delegation_max_amount = 5000
        self.ctx.with_authority_context({"requested_amount": 10000})
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)

    def test_risk_exceeds_limit_rejects(self):
        self.gate.has_authority = True
        self.gate.max_risk = 5000
        self.ctx.with_authority_context({"additional_risk": 10000})
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)

    def test_unknown_authority_fails_closed(self):
        self.ctx.with_authority_context({"state": "UNKNOWN"})
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.BLOCK)

    def test_action_not_in_scope_rejects(self):
        self.gate.has_authority = True
        self.gate.allowed_actions = ["CAPITAL_ALLOCATION"]
        self.ctx.decision_type = "LEVERAGE_CHANGE"
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)

    def test_wildcard_allows_all(self):
        self.gate.has_authority = True
        self.gate.allowed_actions = ["*"]
        self.ctx.decision_type = "ORDER_SUBMIT"
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.PASS)

    def test_revoked_from_context(self):
        self.gate.has_authority = True
        self.ctx.with_authority_context({"revoked": True})
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)


if __name__ == "__main__":
    unittest.main()
