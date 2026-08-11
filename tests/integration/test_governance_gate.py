"""
Tests: Governance Gate
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
    "governance_gate",
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
from services.integration.governance_gate import GovernanceGate


class TestGovernanceGate(unittest.TestCase):
    """Governance gate validation."""

    def setUp(self):
        self.gate = GovernanceGate()
        self.ctx = TradingControlContext(flow_id="FLOW-TEST")

    def test_normal_state_passes(self):
        self.ctx.with_governance_context({"governance_state": "NORMAL"})
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.PASS)

    def test_frozen_state_returns_freeze(self):
        self.gate.frozen = True
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.FREEZE)
        self.assertIn("FROZEN", result.reason)

    def test_frozen_from_context(self):
        self.ctx.with_governance_context({"governance_state": "FROZEN"})
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.FREEZE)

    def test_emergency_mode_allows_risk_reduction(self):
        self.gate.emergency_mode = True
        self.ctx.decision_type = "CAPITAL_DEALLOCATION"
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.PASS)

    def test_emergency_mode_blocks_risk_increase(self):
        self.gate.emergency_mode = True
        self.ctx.decision_type = "CAPITAL_ALLOCATION"
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.BLOCK)

    def test_emergency_mode_allows_emergency_action(self):
        self.gate.emergency_mode = True
        self.ctx.decision_type = "EMERGENCY_ACTION"
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.PASS)

    def test_trading_halted_returns_block(self):
        self.gate.trading_halted = True
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.BLOCK)

    def test_blocked_strategy_returns_reject(self):
        self.ctx.strategy_id = "STRAT-BLOCKED"
        self.gate.blocked_strategies = ["STRAT-BLOCKED"]
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)

    def test_non_blocked_strategy_passes(self):
        self.ctx.strategy_id = "STRAT-OK"
        self.gate.blocked_strategies = ["STRAT-BLOCKED"]
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.PASS)

    def test_policy_violations_return_reject(self):
        self.gate.policy_violations = ["Leverage limit breached"]
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)
        self.assertIn("Leverage limit breached", result.reason)

    def test_unknown_governance_state_fails_closed(self):
        self.ctx.with_governance_context({"governance_state": "UNKNOWN"})
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.BLOCK)

    def test_emergency_from_context_blocks(self):
        self.ctx.with_governance_context({"governance_state": "EMERGENCY"})
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.BLOCK)

    def test_default_state_is_normal(self):
        # No governance context → should pass (default NORMAL)
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.PASS)


if __name__ == "__main__":
    unittest.main()
