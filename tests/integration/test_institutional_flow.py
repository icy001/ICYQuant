"""
Tests: End-to-End Institutional Flow
Commit 21 Part 1.1

Covers:
  - E2E normal path: Signal → Decision → Risk → Governance → Authority → Approval → ORDER_READY
  - Risk Failure
  - Governance Freeze
  - Authority Failure
  - Approval Expired
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
    "control_state", "control_context", "control_transition",
    "control_result", "control_flow",
    "trading_context", "trading_transition", "trading_result", "trading_flow",
    "control_gate", "risk_gate", "governance_gate", "authority_gate", "approval_gate",
    "signal_adapter", "decision_adapter",
    "risk_adapter", "governance_adapter", "authority_adapter", "approval_adapter",
    "order_adapter",
    "flow_orchestrator", "flow_validator", "flow_registry",
    "integration_metrics",
]:
    _fp = os.path.join(_int_dir, f"{_name}.py")
    _spec = importlib.util.spec_from_file_location(
        f"services.integration.{_name}", _fp
    )
    _m = importlib.util.module_from_spec(_spec)
    sys.modules[f"services.integration.{_name}"] = _m
    _spec.loader.exec_module(_m)

from services.integration.control_state import ControlFlowState
from services.integration.control_context import TradingControlContext
from services.integration.control_result import GateStatus
from services.integration.flow_orchestrator import FlowOrchestrator
from services.integration.signal_adapter import SignalInput
from services.integration.risk_adapter import RiskAdapter
from services.integration.governance_adapter import GovernanceAdapter
from services.integration.authority_adapter import AuthorityAdapter
from services.integration.approval_adapter import ApprovalAdapter
from services.integration.trading_result import TradingOutcome


class TestE2EHappyPath(unittest.TestCase):
    """End-to-end normal path: all gates pass."""

    def setUp(self):
        self.orchestrator = FlowOrchestrator()

    def _make_signal(self):
        return SignalInput(
            signal_id="SIG-001",
            strategy_id="STRAT-001",
            portfolio_id="PORT-001",
            symbol="AAPL",
            side="BUY",
            quantity=100,
            price=150.0,
            score=0.85,
            confidence=0.9,
            reason="Momentum signal",
        )

    def _make_normal_risk(self):
        return RiskAdapter.build_risk_context(
            exposure=0.3, leverage=1.5, portfolio_drawdown=0.05,
            concentration_hhi=0.1, liquidity_score=0.9, position_size_pct=0.05,
        )

    def _make_normal_governance(self):
        return GovernanceAdapter.build_governance_context(
            governance_state="NORMAL", emergency_mode=False,
        )

    def _make_authority(self):
        return AuthorityAdapter.build_authority_context(
            authorized=True, max_amount=float("inf"), max_risk=float("inf"),
        )

    def _make_approval(self):
        return ApprovalAdapter.build_approval_context(
            approval_id="APR-001", status="APPROVED", approved_amount=float("inf"),
        )

    def test_e2e_happy_path(self):
        signal = self._make_signal()
        result = self.orchestrator.orchestrate_from_signal(
            signal=signal,
            risk_data=self._make_normal_risk(),
            governance_data=self._make_normal_governance(),
            authority_data=self._make_authority(),
            approval_data=self._make_approval(),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.outcome, TradingOutcome.EXECUTED)
        # Check that all gate results are present
        self.assertIn("risk", result.gate_results)
        self.assertIn("governance", result.gate_results)
        self.assertIn("authority", result.gate_results)
        self.assertIn("approval", result.gate_results)
        # All gates should have passed
        for gate_name, gr in result.gate_results.items():
            self.assertEqual(gr.status, GateStatus.PASS,
                             f"{gate_name} gate should PASS, got {gr.status.name}: {gr.reason}")

    def test_e2e_flow_has_transition_history(self):
        signal = self._make_signal()
        result = self.orchestrator.orchestrate_from_signal(
            signal=signal,
            risk_data=self._make_normal_risk(),
            governance_data=self._make_normal_governance(),
            authority_data=self._make_authority(),
            approval_data=self._make_approval(),
        )
        # Check transition count (VALIDATING + RISK_CHECKED + GOVERNANCE_CHECKED
        # + AUTHORIZED + APPROVED + ORDER_READY + SUBMITTED + EXECUTING + EXECUTED)
        self.assertGreaterEqual(result.transition_count, 4)

    def test_e2e_result_has_flow_id(self):
        signal = self._make_signal()
        result = self.orchestrator.orchestrate_from_signal(
            signal=signal,
            risk_data=self._make_normal_risk(),
            governance_data=self._make_normal_governance(),
            authority_data=self._make_authority(),
            approval_data=self._make_approval(),
        )
        self.assertTrue(result.flow_id.startswith("FLOW-"))

    def test_e2e_result_has_decision_id(self):
        signal = self._make_signal()
        result = self.orchestrator.orchestrate_from_signal(
            signal=signal,
            risk_data=self._make_normal_risk(),
            governance_data=self._make_normal_governance(),
            authority_data=self._make_authority(),
            approval_data=self._make_approval(),
        )
        self.assertEqual(result.decision_id, "")  # No decision_id from signal


class TestE2ERiskFailure(unittest.TestCase):
    """E2E: Risk Gate rejects."""

    def setUp(self):
        self.orchestrator = FlowOrchestrator()

    def test_risk_failure_stops_flow(self):
        signal = SignalInput(
            signal_id="SIG-002",
            strategy_id="STRAT-001",
            symbol="TSLA",
            side="BUY",
            quantity=1000,
            price=200.0,
        )
        # Very high exposure
        risk_data = RiskAdapter.build_risk_context(
            exposure=1.5, leverage=5.0,
        )
        result = self.orchestrator.orchestrate_from_signal(
            signal=signal,
            risk_data=risk_data,
        )
        self.assertFalse(result.success)
        self.assertEqual(result.outcome, TradingOutcome.REJECTED)
        self.assertEqual(result.gate_results["risk"].status, GateStatus.REJECT)


class TestE2EGovernanceFreeze(unittest.TestCase):
    """E2E: Governance Gate freeze."""

    def setUp(self):
        self.orchestrator = FlowOrchestrator()

    def test_governance_freeze_stops_flow(self):
        signal = SignalInput(
            signal_id="SIG-003",
            strategy_id="STRAT-001",
            symbol="MSFT",
            side="BUY",
            quantity=50,
            price=300.0,
        )
        risk_data = RiskAdapter.build_risk_context(
            exposure=0.3, leverage=1.0,
        )
        governance_data = GovernanceAdapter.build_governance_context(
            governance_state="FROZEN",
        )
        result = self.orchestrator.orchestrate_from_signal(
            signal=signal,
            risk_data=risk_data,
            governance_data=governance_data,
        )
        self.assertFalse(result.success)
        self.assertEqual(result.outcome, TradingOutcome.FROZEN)
        self.assertEqual(result.gate_results["governance"].status, GateStatus.FREEZE)


class TestE2EAuthorityFailure(unittest.TestCase):
    """E2E: Authority Gate rejects."""

    def setUp(self):
        self.orchestrator = FlowOrchestrator()

    def test_authority_failure_stops_flow(self):
        signal = SignalInput(
            signal_id="SIG-004",
            strategy_id="STRAT-001",
            symbol="GOOG",
            side="BUY",
            quantity=100,
            price=140.0,
        )
        risk_data = RiskAdapter.build_risk_context(
            exposure=0.3, leverage=1.0,
        )
        governance_data = GovernanceAdapter.build_governance_context(
            governance_state="NORMAL",
        )
        authority_data = AuthorityAdapter.build_authority_context(
            authorized=False, max_amount=0,
        )
        result = self.orchestrator.orchestrate_from_signal(
            signal=signal,
            risk_data=risk_data,
            governance_data=governance_data,
            authority_data=authority_data,
        )
        self.assertFalse(result.success)
        self.assertEqual(result.outcome, TradingOutcome.REJECTED)


class TestE2EApprovalExpired(unittest.TestCase):
    """E2E: Approval Gate expired."""

    def setUp(self):
        self.orchestrator = FlowOrchestrator()

    def test_approval_expired_stops_flow(self):
        signal = SignalInput(
            signal_id="SIG-005",
            strategy_id="STRAT-001",
            symbol="AMZN",
            side="BUY",
            quantity=10,
            price=130.0,
        )
        risk_data = RiskAdapter.build_risk_context(
            exposure=0.3, leverage=1.0,
        )
        governance_data = GovernanceAdapter.build_governance_context(
            governance_state="NORMAL",
        )
        authority_data = AuthorityAdapter.build_authority_context(
            authorized=True, max_amount=float("inf"),
        )
        approval_data = ApprovalAdapter.build_approval_context(
            approval_id="APR-EXP", status="EXPIRED",
        )
        result = self.orchestrator.orchestrate_from_signal(
            signal=signal,
            risk_data=risk_data,
            governance_data=governance_data,
            authority_data=authority_data,
            approval_data=approval_data,
        )
        self.assertFalse(result.success)
        self.assertEqual(result.outcome, TradingOutcome.EXPIRED)


class TestFlowRegistry(unittest.TestCase):
    """Flow registry idempotency and tracking."""

    def setUp(self):
        from services.integration.flow_registry import FlowRegistry
        from services.integration.trading_flow import TradingFlow
        self.registry = FlowRegistry()

    def test_register_new_flow(self):
        from services.integration.trading_flow import TradingFlow
        flow = TradingFlow()
        self.assertTrue(self.registry.register(flow))

    def test_duplicate_flow_rejected(self):
        from services.integration.trading_flow import TradingFlow
        flow = TradingFlow()
        self.assertTrue(self.registry.register(flow))
        self.assertFalse(self.registry.register(flow))

    def test_idempotency_key(self):
        self.assertTrue(self.registry.register_idempotency_key("F-1", "KEY-1"))
        self.assertFalse(self.registry.register_idempotency_key("F-2", "KEY-1"))
        self.assertTrue(self.registry.is_duplicate("KEY-1"))

    def test_stats(self):
        from services.integration.trading_flow import TradingFlow
        flow = TradingFlow()
        self.registry.register(flow)
        self.registry.complete(flow.flow_id)
        stats = self.registry.stats()
        self.assertEqual(stats["total_flows"], 1)
        self.assertEqual(stats["completed_flows"], 1)


if __name__ == "__main__":
    unittest.main()
