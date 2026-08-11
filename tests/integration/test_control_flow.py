"""
Tests: Control Flow State Machine
Commit 21 Part 1.1
"""

import sys
import os
import unittest
import types
import importlib.util
import time

# ── Virtual package bootstrap ──────────────────────────────────
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

# Load integration modules
for _name in [
    "control_state", "control_context", "control_transition",
    "control_result", "control_flow",
]:
    _fp = os.path.join(_int_dir, f"{_name}.py")
    _spec = importlib.util.spec_from_file_location(
        f"services.integration.{_name}", _fp
    )
    _m = importlib.util.module_from_spec(_spec)
    sys.modules[f"services.integration.{_name}"] = _m
    _spec.loader.exec_module(_m)

from services.integration.control_state import (
    ControlFlowState,
    can_transition,
    valid_transitions_from,
    is_fail_closed_state,
    VALID_CONTROL_TRANSITIONS,
)
from services.integration.control_context import TradingControlContext
from services.integration.control_transition import ControlTransition
from services.integration.control_result import ControlResult, GateStatus
from services.integration.control_flow import ControlFlow


class TestControlFlowState(unittest.TestCase):
    """ControlFlowState enum properties."""

    def test_happy_path_states_are_not_terminal(self):
        happy = [
            ControlFlowState.PROPOSED,
            ControlFlowState.VALIDATING,
            ControlFlowState.RISK_CHECKED,
            ControlFlowState.GOVERNANCE_CHECKED,
            ControlFlowState.AUTHORIZED,
            ControlFlowState.APPROVED,
            ControlFlowState.ORDER_READY,
            ControlFlowState.SUBMITTED,
            ControlFlowState.EXECUTING,
        ]
        for s in happy:
            self.assertFalse(s.is_terminal, f"{s.name} should not be terminal")

    def test_terminal_states(self):
        terminal = [
            ControlFlowState.EXECUTED,
            ControlFlowState.REJECTED,
            ControlFlowState.BLOCKED,
            ControlFlowState.FROZEN,
            ControlFlowState.CANCELLED,
            ControlFlowState.EXPIRED,
            ControlFlowState.FAILED,
        ]
        for s in terminal:
            self.assertTrue(s.is_terminal, f"{s.name} should be terminal")

    def test_active_states(self):
        active = [
            ControlFlowState.PROPOSED,
            ControlFlowState.VALIDATING,
            ControlFlowState.RISK_CHECKED,
        ]
        for s in active:
            self.assertTrue(s.is_active)

    def test_executed_is_terminal(self):
        self.assertTrue(ControlFlowState.EXECUTED.is_terminal)
        self.assertFalse(ControlFlowState.EXECUTED.is_active)

    def test_is_fail_closed_state(self):
        self.assertTrue(is_fail_closed_state(ControlFlowState.BLOCKED))
        self.assertTrue(is_fail_closed_state(ControlFlowState.FROZEN))
        self.assertTrue(is_fail_closed_state(ControlFlowState.FAILED))
        self.assertFalse(is_fail_closed_state(ControlFlowState.PROPOSED))
        self.assertFalse(is_fail_closed_state(ControlFlowState.EXECUTED))


class TestControlTransitions(unittest.TestCase):
    """Valid state transitions."""

    def test_happy_path_chain(self):
        chain = [
            ControlFlowState.PROPOSED,
            ControlFlowState.VALIDATING,
            ControlFlowState.RISK_CHECKED,
            ControlFlowState.GOVERNANCE_CHECKED,
            ControlFlowState.AUTHORIZED,
            ControlFlowState.APPROVED,
            ControlFlowState.ORDER_READY,
        ]
        for i in range(len(chain) - 1):
            self.assertTrue(
                can_transition(chain[i], chain[i + 1]),
                f"{chain[i].name} → {chain[i+1].name} should be valid",
            )

    def test_proposed_directly_to_approved_is_invalid(self):
        self.assertFalse(can_transition(
            ControlFlowState.PROPOSED, ControlFlowState.APPROVED
        ))

    def test_rejected_cannot_proceed(self):
        self.assertFalse(can_transition(
            ControlFlowState.REJECTED, ControlFlowState.APPROVED
        ))

    def test_executed_has_no_outgoing(self):
        self.assertEqual(
            len(valid_transitions_from(ControlFlowState.EXECUTED)), 0
        )

    def test_blocked_has_no_outgoing(self):
        self.assertEqual(
            len(valid_transitions_from(ControlFlowState.BLOCKED)), 0
        )

    def test_freezing_is_valid_from_governance_checked(self):
        self.assertTrue(can_transition(
            ControlFlowState.GOVERNANCE_CHECKED, ControlFlowState.FROZEN
        ))

    def test_expiry_from_approved(self):
        self.assertTrue(can_transition(
            ControlFlowState.APPROVED, ControlFlowState.EXPIRED
        ))


class TestControlFlowMachine(unittest.TestCase):
    """ControlFlow state machine behavior."""

    def setUp(self):
        self.flow = ControlFlow()

    def test_initial_state_is_proposed(self):
        self.assertEqual(self.flow.current_state, ControlFlowState.PROPOSED)

    def test_advance_to_validating(self):
        t = self.flow.advance_to_validating(reason="test")
        self.assertEqual(t.to_state, ControlFlowState.VALIDATING)
        self.assertEqual(self.flow.current_state, ControlFlowState.VALIDATING)

    def test_full_happy_path(self):
        self.flow.advance_to_validating()
        self.flow.advance_to_risk_checked()
        self.flow.advance_to_governance_checked()
        self.flow.advance_to_authorized()
        self.flow.advance_to_approved()
        self.flow.advance_to_order_ready()
        self.assertEqual(self.flow.current_state, ControlFlowState.ORDER_READY)
        self.assertEqual(len(self.flow.transitions), 6)

    def test_invalid_transition_raises(self):
        with self.assertRaises(ValueError):
            self.flow.transition(ControlFlowState.APPROVED)

    def test_reject_from_validating(self):
        self.flow.advance_to_validating()
        self.flow.reject(reason="Risk too high")
        self.assertEqual(self.flow.current_state, ControlFlowState.REJECTED)
        self.assertTrue(self.flow.is_terminal)

    def test_block_from_risk_checked(self):
        self.flow.advance_to_validating()
        self.flow.advance_to_risk_checked()
        self.flow.block(reason="System degraded")
        self.assertEqual(self.flow.current_state, ControlFlowState.BLOCKED)

    def test_freeze_from_governance_checked(self):
        self.flow.advance_to_validating()
        self.flow.advance_to_risk_checked()
        self.flow.advance_to_governance_checked()
        self.flow.freeze(reason="Governance freeze")
        self.assertEqual(self.flow.current_state, ControlFlowState.FROZEN)

    def test_cancel_from_proposed(self):
        self.flow.cancel(reason="No longer needed")
        self.assertEqual(self.flow.current_state, ControlFlowState.CANCELLED)

    def test_transition_records_policy_version(self):
        self.flow.context.policy_version = "POLICY-v7"
        t = self.flow.advance_to_validating()
        self.assertEqual(t.policy_version, "POLICY-v7")

    def test_transition_has_transition_id(self):
        t = self.flow.advance_to_validating()
        self.assertTrue(t.transition_id.startswith("CT-"))

    def test_summary(self):
        self.flow.advance_to_validating()
        s = self.flow.summary()
        self.assertEqual(s["current_state"], "VALIDATING")
        self.assertEqual(s["transition_count"], 1)


class TestIdempotency(unittest.TestCase):
    """Idempotency key handling."""

    def setUp(self):
        self.flow = ControlFlow()

    def test_first_key_is_accepted(self):
        self.assertTrue(self.flow.ensure_idempotent("key-001"))

    def test_duplicate_key_is_rejected(self):
        self.assertTrue(self.flow.ensure_idempotent("key-001"))
        self.assertFalse(self.flow.ensure_idempotent("key-001"))

    def test_is_duplicate(self):
        self.flow.ensure_idempotent("key-002")
        self.assertTrue(self.flow.is_duplicate("key-002"))
        self.assertFalse(self.flow.is_duplicate("key-003"))


class TestGateResults(unittest.TestCase):
    """Recording and retrieving gate results."""

    def setUp(self):
        self.flow = ControlFlow()

    def test_record_and_retrieve(self):
        result = ControlResult.make_pass(flow_id=self.flow.flow_id, reason="OK")
        self.flow.record_gate_result("risk", result)
        retrieved = self.flow.get_gate_result("risk")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.status, GateStatus.PASS)

    def test_missing_gate_returns_none(self):
        self.assertIsNone(self.flow.get_gate_result("nonexistent"))


if __name__ == "__main__":
    unittest.main()
