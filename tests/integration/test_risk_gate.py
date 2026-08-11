"""
Tests: Risk Gate
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
    "risk_gate",
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
from services.integration.risk_gate import RiskGate, RiskGateConfig


class TestRiskGate(unittest.TestCase):
    """Risk gate constraint validation."""

    def setUp(self):
        self.gate = RiskGate()
        self.ctx = TradingControlContext(flow_id="FLOW-TEST")

    def test_password_with_all_normal_metrics(self):
        self.ctx.with_risk_context({
            "exposure": 0.5,
            "leverage": 1.5,
            "drawdown": 0.05,
            "concentration": 0.1,
            "liquidity": 0.8,
            "position_size": 0.05,
        })
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.PASS)

    def test_exposure_too_high_returns_reject(self):
        self.gate.config.max_exposure_pct = 0.8
        self.ctx.with_risk_context({"exposure": 0.95})
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)
        self.assertIn("Exposure", result.reason)

    def test_leverage_too_high_returns_reject(self):
        self.gate.config.max_leverage = 2.0
        self.ctx.with_risk_context({"leverage": 3.5, "exposure": 0.1})
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)
        self.assertIn("Leverage", result.reason)

    def test_drawdown_too_high_returns_reject(self):
        self.gate.config.max_drawdown_pct = 0.10
        self.ctx.with_risk_context({
            "exposure": 0.1,
            "leverage": 1.0,
            "drawdown": 0.25,
        })
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)
        self.assertIn("Drawdown", result.reason)

    def test_concentration_too_high_returns_reject(self):
        self.gate.config.max_concentration_pct = 0.20
        self.ctx.with_risk_context({
            "exposure": 0.1,
            "leverage": 1.0,
            "drawdown": 0.0,
            "concentration": 0.30,
        })
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)
        self.assertIn("Concentration", result.reason)

    def test_liquidity_too_low_returns_reject(self):
        self.gate.config.min_liquidity_score = 0.5
        self.ctx.with_risk_context({
            "exposure": 0.1,
            "leverage": 1.0,
            "drawdown": 0.0,
            "liquidity": 0.2,
        })
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)
        self.assertIn("Liquidity", result.reason)

    def test_position_size_too_high_returns_reject(self):
        self.gate.config.max_position_size_pct = 0.05
        self.ctx.with_risk_context({
            "exposure": 0.1,
            "leverage": 1.0,
            "drawdown": 0.0,
            "position_size": 0.15,
        })
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)

    def test_no_risk_context_returns_block_fail_closed(self):
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.BLOCK)
        self.assertIn("No risk context", result.reason)

    def test_multiple_violations_report_all(self):
        self.gate.config.max_exposure_pct = 0.3
        self.gate.config.max_leverage = 1.0
        self.ctx.with_risk_context({
            "exposure": 0.8,
            "leverage": 3.0,
        })
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.REJECT)
        self.assertIn("Exposure", result.reason)
        self.assertIn("Leverage", result.reason)

    def test_disabled_checks_skip(self):
        self.gate.config.enabled_checks["drawdown"] = False
        self.ctx.with_risk_context({
            "exposure": 0.1,
            "leverage": 1.0,
            "drawdown": 0.50,
        })
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.PASS)

    def test_alternate_field_names(self):
        self.ctx.with_risk_context({
            "exposure": 0.3,
            "leverage_ratio": 1.2,
            "portfolio_drawdown": 0.05,
            "concentration_hhi": 0.1,
            "liquidity_score": 0.9,
            "position_size_pct": 0.03,
        })
        result = self.gate.check(self.ctx)
        self.assertEqual(result.status, GateStatus.PASS)


if __name__ == "__main__":
    unittest.main()
