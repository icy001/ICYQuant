"""
Tests: Flow Validator
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
    "control_state", "control_context", "control_transition",
    "control_result", "control_flow",
    "trading_context", "trading_transition", "trading_result", "trading_flow",
    "control_gate", "risk_gate", "governance_gate", "authority_gate", "approval_gate",
    "flow_orchestrator", "flow_validator", "flow_registry",
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
from services.integration.control_flow import ControlFlow
from services.integration.control_result import ControlResult, GateStatus
from services.integration.flow_validator import FlowValidator


class TestFlowValidator(unittest.TestCase):
    """Integration invariant validation."""

    def setUp(self):
        self.validator = FlowValidator()

    def _make_flow(self, decision_id="DEC-001", flow_id="FLOW-001"):
        ctx = TradingControlContext(
            flow_id=flow_id,
            decision_id=decision_id,
        )
        return ControlFlow(flow_id=flow_id, context=ctx)

    def test_valid_flow_passes_all_invariants(self):
        flow = self._make_flow()
        flow.advance_to_validating()

        # Set contexts so invariant 7 doesn't flag passing gates
        flow.context.with_risk_context({"exposure": 0.3})
        flow.context.with_governance_context({"state": "NORMAL"})
        flow.context.with_authority_context({"authorized": True})
        flow.context.with_approval_context({"status": "APPROVED"})

        flow.record_gate_result("risk", ControlResult.make_pass(flow_id=flow.flow_id))
        flow.advance_to_risk_checked()
        flow.record_gate_result("governance", ControlResult.make_pass(flow_id=flow.flow_id))
        flow.advance_to_governance_checked()
        flow.record_gate_result("authority", ControlResult.make_pass(flow_id=flow.flow_id))
        flow.advance_to_authorized()
        flow.record_gate_result("approval", ControlResult.make_pass(flow_id=flow.flow_id))
        flow.advance_to_approved()
        flow.advance_to_order_ready()

        result = self.validator.validate(flow)
        self.assertTrue(result.valid, f"Violations: {[(v.invariant_id, v.detail) for v in result.violations]}")

    def test_missing_decision_id_violates_invariant_1(self):
        flow = self._make_flow(decision_id="")
        result = self.validator.validate(flow)
        self.assertFalse(result.valid)
        self.assertTrue(any(v.invariant_id == 1 for v in result.violations))

    def test_missing_risk_gate_result_violates_invariant_2(self):
        flow = self._make_flow()
        # Force state to beyond risk_checked without recording gate result
        flow.advance_to_validating()
        flow.advance_to_risk_checked()
        flow.advance_to_governance_checked()
        flow.advance_to_authorized()

        result = self.validator.validate(flow)
        self.assertTrue(any(v.invariant_id == 2 for v in result.violations))

    def test_missing_governance_gate_result_violates_invariant_3(self):
        flow = self._make_flow()
        flow.advance_to_validating()
        flow.advance_to_risk_checked()
        flow.advance_to_governance_checked()
        flow.advance_to_authorized()
        flow.advance_to_approved()

        result = self.validator.validate(flow)
        self.assertTrue(any(v.invariant_id == 3 for v in result.violations))

    def test_missing_authority_gate_result_violates_invariant_4(self):
        flow = self._make_flow()
        flow.advance_to_validating()
        flow.advance_to_risk_checked()
        flow.advance_to_governance_checked()
        flow.advance_to_authorized()
        flow.advance_to_approved()
        flow.advance_to_order_ready()

        result = self.validator.validate(flow)
        self.assertTrue(any(v.invariant_id == 4 for v in result.violations))

    def test_validate_transition_chain(self):
        valid_chain = [
            ControlFlowState.PROPOSED,
            ControlFlowState.VALIDATING,
            ControlFlowState.RISK_CHECKED,
        ]
        self.assertTrue(FlowValidator.validate_transition_chain(valid_chain))

    def test_invalid_transition_chain(self):
        invalid_chain = [
            ControlFlowState.PROPOSED,
            ControlFlowState.APPROVED,
        ]
        self.assertFalse(FlowValidator.validate_transition_chain(invalid_chain))

    def test_assert_no_bypass_raises(self):
        with self.assertRaises(ValueError):
            FlowValidator.assert_no_bypass(
                ControlFlowState.PROPOSED, ControlFlowState.APPROVED
            )

    def test_assert_no_bypass_passes_for_valid(self):
        # Should not raise
        FlowValidator.assert_no_bypass(
            ControlFlowState.VALIDATING, ControlFlowState.RISK_CHECKED
        )

    def test_flow_with_gate_results_passes(self):
        flow = self._make_flow()
        flow.advance_to_validating()

        # Set contexts so invariant 7 doesn't flag passing gates without context
        flow.context.with_risk_context({"exposure": 0.3})
        flow.context.with_governance_context({"state": "NORMAL"})
        flow.context.with_authority_context({"authorized": True})
        flow.context.with_approval_context({"status": "APPROVED"})

        # Record risk gate result
        flow.record_gate_result("risk", ControlResult.make_pass(flow_id=flow.flow_id))
        flow.advance_to_risk_checked()

        # Record governance gate result
        flow.record_gate_result("governance", ControlResult.make_pass(flow_id=flow.flow_id))
        flow.advance_to_governance_checked()

        # Record authority gate result
        flow.record_gate_result("authority", ControlResult.make_pass(flow_id=flow.flow_id))
        flow.advance_to_authorized()

        # Record approval gate result
        flow.record_gate_result("approval", ControlResult.make_pass(flow_id=flow.flow_id))
        flow.advance_to_approved()
        flow.advance_to_order_ready()

        result = self.validator.validate(flow)
        self.assertTrue(result.valid,
                        f"Violations: {[(v.invariant_id, v.detail) for v in result.violations]}")

    def test_flow_without_flow_id_violates_invariant_10(self):
        ctx = TradingControlContext(flow_id="", decision_id="DEC-001")
        flow = ControlFlow(flow_id="", context=ctx)
        result = self.validator.validate(flow)
        self.assertTrue(any(v.invariant_id == 10 for v in result.violations))

    def test_all_10_invariants_defined(self):
        self.assertEqual(len(FlowValidator.INVARIANTS), 10)

    def test_approval_not_required_does_not_violate_5(self):
        flow = self._make_flow()
        flow.advance_to_validating()
        flow.record_gate_result("risk", ControlResult.make_pass(flow_id=flow.flow_id))
        flow.advance_to_risk_checked()
        flow.record_gate_result("governance", ControlResult.make_pass(flow_id=flow.flow_id))
        flow.advance_to_governance_checked()
        flow.record_gate_result("authority", ControlResult.make_pass(flow_id=flow.flow_id))
        flow.advance_to_authorized()
        flow.advance_to_approved()
        flow.advance_to_order_ready()

        # No approval_context set → invariant 5 should not trigger
        result = self.validator.validate(flow)
        self.assertFalse(any(v.invariant_id == 5 for v in result.violations))


if __name__ == "__main__":
    unittest.main()
