"""
Flow Validator — validates invariants throughout the institutional control flow.

Commit 21 Part 1.1: enforces all 10 integration invariants:
  1. Every order must originate from a valid decision.
  2. Every decision must pass Risk Gate.
  3. Every decision must pass Governance Gate.
  4. Every order must have valid authority.
  5. Every order must have valid approval when required.
  6. Gate failure cannot be bypassed by downstream services.
  7. Unknown critical state fails closed.
  8. Every transition is idempotent.
  9. Every transition is auditable.
  10. Every order must retain the originating flow_id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .control_flow import ControlFlow
from .control_state import ControlFlowState, can_transition
from .control_context import TradingControlContext
from .control_result import ControlResult, GateStatus


@dataclass
class InvariantViolation:
    """Record of a broken integration invariant."""
    invariant_id: int
    description: str
    detail: str
    severity: str = "ERROR"  # ERROR / WARNING


@dataclass
class FlowValidationResult:
    """Result of flow validation."""
    valid: bool = True
    violations: List[InvariantViolation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_violation(self, invariant_id: int, description: str, detail: str,
                      severity: str = "ERROR") -> None:
        self.violations.append(InvariantViolation(
            invariant_id=invariant_id,
            description=description,
            detail=detail,
            severity=severity,
        ))
        if severity == "ERROR":
            self.valid = False

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


class FlowValidator:
    """Validates all integration invariants against a control flow."""

    # ── The 10 Invariants ──────────────────────────────────────

    INVARIANTS = {
        1: "Every order must originate from a valid decision.",
        2: "Every decision must pass Risk Gate.",
        3: "Every decision must pass Governance Gate.",
        4: "Every order must have valid authority.",
        5: "Every order must have valid approval when required.",
        6: "Gate failure cannot be bypassed by downstream services.",
        7: "Unknown critical state fails closed.",
        8: "Every transition is idempotent.",
        9: "Every transition is auditable.",
        10: "Every order must retain the originating flow_id.",
    }

    def validate(self, flow: ControlFlow) -> FlowValidationResult:
        """Run all invariant checks against a flow."""
        result = FlowValidationResult()

        self._check_decision_origin(flow, result)     # 1
        self._check_risk_gate(flow, result)           # 2
        self._check_governance_gate(flow, result)     # 3
        self._check_authority(flow, result)           # 4
        self._check_approval(flow, result)            # 5
        self._check_no_gate_bypass(flow, result)      # 6
        self._check_fail_closed(flow, result)         # 7
        self._check_idempotency(flow, result)         # 8
        self._check_auditability(flow, result)        # 9
        self._check_flow_id(flow, result)             # 10

        return result

    # ── Invariant Checks ──────────────────────────────────────

    def _check_decision_origin(self, flow: ControlFlow, result: FlowValidationResult) -> None:
        """Invariant 1: Every order must originate from a valid decision."""
        if not flow.context.decision_id:
            result.add_violation(1, self.INVARIANTS[1],
                                 "No decision_id in flow context — order has no valid origin")

    def _check_risk_gate(self, flow: ControlFlow, result: FlowValidationResult) -> None:
        """Invariant 2: Every decision must pass Risk Gate."""
        adv_states = [ControlFlowState.GOVERNANCE_CHECKED, ControlFlowState.AUTHORIZED,
                      ControlFlowState.APPROVED, ControlFlowState.ORDER_READY,
                      ControlFlowState.SUBMITTED, ControlFlowState.EXECUTING,
                      ControlFlowState.EXECUTED]
        if flow.current_state in adv_states:
            risk_result = flow.get_gate_result("risk")
            if risk_result is None or not risk_result.passed:
                result.add_violation(2, self.INVARIANTS[2],
                                     "Advanced past Risk Gate without PASS result")

    def _check_governance_gate(self, flow: ControlFlow, result: FlowValidationResult) -> None:
        """Invariant 3: Every decision must pass Governance Gate."""
        adv_states = [ControlFlowState.AUTHORIZED, ControlFlowState.APPROVED,
                      ControlFlowState.ORDER_READY, ControlFlowState.SUBMITTED,
                      ControlFlowState.EXECUTING, ControlFlowState.EXECUTED]
        if flow.current_state in adv_states:
            gov_result = flow.get_gate_result("governance")
            if gov_result is None or not gov_result.passed:
                result.add_violation(3, self.INVARIANTS[3],
                                     "Advanced past Governance Gate without PASS result")

    def _check_authority(self, flow: ControlFlow, result: FlowValidationResult) -> None:
        """Invariant 4: Every order must have valid authority."""
        adv_states = [ControlFlowState.APPROVED, ControlFlowState.ORDER_READY,
                      ControlFlowState.SUBMITTED, ControlFlowState.EXECUTING,
                      ControlFlowState.EXECUTED]
        if flow.current_state in adv_states:
            auth_result = flow.get_gate_result("authority")
            if auth_result is None or not auth_result.passed:
                result.add_violation(4, self.INVARIANTS[4],
                                     "Advanced past Authority Gate without PASS result")

    def _check_approval(self, flow: ControlFlow, result: FlowValidationResult) -> None:
        """Invariant 5: Every order must have valid approval when required."""
        # Only check if approval context exists (approval may not be required)
        if flow.context.approval_context:
            adv_states = [ControlFlowState.ORDER_READY, ControlFlowState.SUBMITTED,
                          ControlFlowState.EXECUTING, ControlFlowState.EXECUTED]
            if flow.current_state in adv_states:
                app_result = flow.get_gate_result("approval")
                if app_result is None or not app_result.passed:
                    result.add_violation(5, self.INVARIANTS[5],
                                         "Advanced past Approval Gate without PASS result "
                                         "(approval was required)")

    def _check_no_gate_bypass(self, flow: ControlFlow, result: FlowValidationResult) -> None:
        """Invariant 6: Gate failure cannot be bypassed by downstream services."""
        states = [t.to_state for t in flow.transitions]
        # Check if any skipped state appears
        required_order = [
            ControlFlowState.PROPOSED,
            ControlFlowState.VALIDATING,
            ControlFlowState.RISK_CHECKED,
            ControlFlowState.GOVERNANCE_CHECKED,
            ControlFlowState.AUTHORIZED,
            ControlFlowState.APPROVED,
        ]
        for i, required in enumerate(required_order):
            if i > 0:
                prev_idx = None
                cur_idx = None
                for j, s in enumerate(states):
                    if s == required_order[i - 1]:
                        prev_idx = j
                    if s == required:
                        cur_idx = j
                if cur_idx is not None and prev_idx is not None and cur_idx < prev_idx:
                    result.add_violation(6, self.INVARIANTS[6],
                                         f"Gate order violation: {required_order[i-1].name} "
                                         f"appeared after {required.name}")

    def _check_fail_closed(self, flow: ControlFlow, result: FlowValidationResult) -> None:
        """Invariant 7: Unknown critical state fails closed."""
        # Check that gates with missing context returned BLOCK, not PASS
        for gate_name in ["risk", "governance", "authority", "approval"]:
            gr = flow.get_gate_result(gate_name)
            if gr is not None and gr.status == GateStatus.PASS:
                # If context was empty and gate returned PASS, that's a violation
                ctx_attr = f"{gate_name}_context"
                ctx = getattr(flow.context, ctx_attr, None)
                if ctx is None:
                    result.add_violation(7, self.INVARIANTS[7],
                                         f"{gate_name} gate returned PASS with no context "
                                         f"(should be BLOCK — fail-closed)")

    def _check_idempotency(self, flow: ControlFlow, result: FlowValidationResult) -> None:
        """Invariant 8: Every transition is idempotent."""
        # Check no duplicate transitions from same state
        seen = set()
        for t in flow.transitions:
            key = (t.from_state, t.to_state)
            if key in seen:
                result.add_warning(f"Duplicate transition: {t.from_state.name} → {t.to_state.name}")
            seen.add(key)

    def _check_auditability(self, flow: ControlFlow, result: FlowValidationResult) -> None:
        """Invariant 9: Every transition is auditable."""
        for t in flow.transitions:
            if not t.transition_id:
                result.add_violation(9, self.INVARIANTS[9],
                                     "Transition has no transition_id")
            if not t.timestamp:
                result.add_violation(9, self.INVARIANTS[9],
                                     "Transition has no timestamp")

    def _check_flow_id(self, flow: ControlFlow, result: FlowValidationResult) -> None:
        """Invariant 10: Every order must retain the originating flow_id."""
        if not flow.context.flow_id:
            result.add_violation(10, self.INVARIANTS[10],
                                 "No flow_id in context — order cannot retain origin")

    # ── State Machine Validation ───────────────────────────────

    @staticmethod
    def validate_transition(from_state: ControlFlowState,
                            to_state: ControlFlowState) -> bool:
        """Check if a single transition is valid per state machine."""
        return can_transition(from_state, to_state)

    @staticmethod
    def validate_transition_chain(states: List[ControlFlowState]) -> bool:
        """Check if a chain of states respects the transition rules."""
        for i in range(len(states) - 1):
            if not can_transition(states[i], states[i + 1]):
                return False
        return True

    # ── Quick Assertions ──────────────────────────────────────

    @staticmethod
    def assert_no_bypass(from_state: ControlFlowState,
                         to_state: ControlFlowState) -> None:
        """Assert that a transition does not bypass gates."""
        direct_bypasses = [
            (ControlFlowState.PROPOSED, ControlFlowState.APPROVED),
            (ControlFlowState.PROPOSED, ControlFlowState.ORDER_READY),
            (ControlFlowState.VALIDATING, ControlFlowState.APPROVED),
            (ControlFlowState.VALIDATING, ControlFlowState.ORDER_READY),
            (ControlFlowState.RISK_CHECKED, ControlFlowState.ORDER_READY),
        ]
        if (from_state, to_state) in direct_bypasses:
            raise ValueError(
                f"Gate bypass: {from_state.name} → {to_state.name} is not allowed "
                f"(must pass through intermediate gates)"
            )
