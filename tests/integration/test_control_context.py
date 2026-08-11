"""
Tests: Control Context
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

for _name in ["control_state", "control_context", "control_result", "control_gate",
              "risk_gate", "governance_gate", "authority_gate", "approval_gate"]:
    _fp = os.path.join(_int_dir, f"{_name}.py")
    _spec = importlib.util.spec_from_file_location(
        f"services.integration.{_name}", _fp
    )
    _m = importlib.util.module_from_spec(_spec)
    sys.modules[f"services.integration.{_name}"] = _m
    _spec.loader.exec_module(_m)

from services.integration.control_context import TradingControlContext
from services.integration.control_result import ControlResult, GateStatus


class TestControlContext(unittest.TestCase):
    """TradingControlContext construction and chaining."""

    def test_flow_id_is_generated(self):
        ctx = TradingControlContext()
        self.assertTrue(ctx.flow_id.startswith("FLOW-"))

    def test_custom_flow_id(self):
        ctx = TradingControlContext(flow_id="MY-FLOW-001")
        self.assertEqual(ctx.flow_id, "MY-FLOW-001")

    def test_touch_updates_timestamp(self):
        ctx = TradingControlContext()
        old_ts = ctx.updated_at
        time.sleep(0.01)
        ctx.touch()
        self.assertGreater(ctx.updated_at, old_ts)

    def test_with_risk_context_chaining(self):
        ctx = TradingControlContext()
        result = ctx.with_risk_context({"exposure": 0.5})
        self.assertIs(result, ctx)
        self.assertEqual(ctx.risk_context["exposure"], 0.5)

    def test_with_governance_context_chaining(self):
        ctx = TradingControlContext()
        ctx.with_governance_context({"state": "NORMAL"})
        self.assertEqual(ctx.governance_context["state"], "NORMAL")

    def test_with_authority_context(self):
        ctx = TradingControlContext()
        ctx.with_authority_context({"authorized": True})
        self.assertTrue(ctx.authority_context["authorized"])

    def test_with_approval_context(self):
        ctx = TradingControlContext()
        ctx.with_approval_context({"status": "APPROVED"})
        self.assertEqual(ctx.approval_context["status"], "APPROVED")

    def test_from_decision_factory(self):
        ctx = TradingControlContext.from_decision(
            decision_id="DEC-001",
            strategy_id="STRAT-001",
            actor="SYSTEM",
            decision_type="ORDER_SUBMIT",
        )
        self.assertEqual(ctx.decision_id, "DEC-001")
        self.assertEqual(ctx.strategy_id, "STRAT-001")

    def test_to_dict(self):
        ctx = TradingControlContext(
            decision_id="DEC-001",
            strategy_id="STRAT-001",
            policy_version="POLICY-v7",
        )
        d = ctx.to_dict()
        self.assertEqual(d["decision_id"], "DEC-001")
        self.assertEqual(d["policy_version"], "POLICY-v7")

    def test_default_values(self):
        ctx = TradingControlContext()
        self.assertIsNone(ctx.strategy_id)
        self.assertIsNone(ctx.signal_id)
        self.assertIsNone(ctx.decision_id)
        self.assertEqual(ctx.actor, "SYSTEM")

    def test_version_pinning(self):
        ctx = TradingControlContext(
            policy_version="POLICY-v7",
            risk_version="RISK-v3",
            governance_version="GOV-v2",
        )
        self.assertEqual(ctx.policy_version, "POLICY-v7")
        self.assertEqual(ctx.risk_version, "RISK-v3")
        self.assertEqual(ctx.governance_version, "GOV-v2")

    def test_idempotency_key(self):
        ctx = TradingControlContext(idempotency_key="IDEM-001")
        self.assertEqual(ctx.idempotency_key, "IDEM-001")


class TestControlResult(unittest.TestCase):
    """ControlResult factory methods and properties."""

    def test_passed(self):
        r = ControlResult.make_pass(flow_id="F-1", reason="OK")
        self.assertEqual(r.status, GateStatus.PASS)
        self.assertTrue(r.passed)

    def test_rejected(self):
        r = ControlResult.make_reject(flow_id="F-1", code="RISK_HIGH", reason="Too risky")
        self.assertEqual(r.status, GateStatus.REJECT)
        self.assertFalse(r.passed)
        self.assertTrue(r.is_terminal)

    def test_blocked(self):
        r = ControlResult.make_block(flow_id="F-1", code="GOV_FROZEN", reason="Frozen")
        self.assertEqual(r.status, GateStatus.BLOCK)

    def test_frozen(self):
        r = ControlResult.make_freeze(flow_id="F-1", reason="Governance freeze")
        self.assertEqual(r.status, GateStatus.FREEZE)

    def test_expired(self):
        r = ControlResult.make_expired(flow_id="F-1", reason="Approval expired")
        self.assertEqual(r.status, GateStatus.EXPIRED)

    def test_error(self):
        r = ControlResult.make_error(flow_id="F-1", reason="Timeout")
        self.assertEqual(r.status, GateStatus.ERROR)

    def test_terminal_states(self):
        for status in [GateStatus.REJECT, GateStatus.BLOCK, GateStatus.FREEZE,
                        GateStatus.EXPIRED, GateStatus.ERROR]:
            self.assertTrue(status.is_terminal, f"{status} should be terminal")

    def test_pass_is_not_terminal(self):
        self.assertFalse(GateStatus.PASS.is_terminal)

    def test_to_dict(self):
        r = ControlResult.make_reject(flow_id="F-1", code="AUTH_DENIED",
                                   reason="No authority", decision_id="D-1")
        d = r.to_dict()
        self.assertEqual(d["status"], "REJECT")
        self.assertEqual(d["code"], "AUTH_DENIED")
        self.assertEqual(d["decision_id"], "D-1")


if __name__ == "__main__":
    unittest.main()
