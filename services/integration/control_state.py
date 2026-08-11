"""
Control Flow State — unified trading control lifecycle states.

Commit 21 Part 1.1: defines the canonical state machine for every
trade/order/decision as it flows through the institutional control pipeline.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Dict, List


class ControlFlowState(Enum):
    """Unified trading control flow state.

    Happy path:  PROPOSED → VALIDATING → RISK_CHECKED → GOVERNANCE_CHECKED
                 → AUTHORIZED → APPROVED → ORDER_READY → SUBMITTED
                 → EXECUTING → EXECUTED

    Error paths: REJECTED / BLOCKED / FROZEN / CANCELLED / EXPIRED / FAILED
    """

    # ── Lifecycle ──────────────────────────────────────────────
    PROPOSED = auto()           # Decision created, not yet validated
    VALIDATING = auto()         # Pre-check validation in progress
    RISK_CHECKED = auto()       # Risk Gate passed
    GOVERNANCE_CHECKED = auto() # Governance Gate passed
    AUTHORIZED = auto()         # Authority Gate passed
    APPROVED = auto()           # Approval Gate passed
    ORDER_READY = auto()        # Ready for order submission
    SUBMITTED = auto()          # Order submitted to exchange/broker
    EXECUTING = auto()          # Order being filled
    EXECUTED = auto()           # Order fully executed

    # ── Terminal / Error ───────────────────────────────────────
    REJECTED = auto()           # Gate rejected
    BLOCKED = auto()            # Gate blocked (fail-closed)
    FROZEN = auto()             # Governance freeze
    CANCELLED = auto()          # Manual cancellation
    EXPIRED = auto()            # Approval / authority expired
    FAILED = auto()             # Technical failure

    # ── Properties ─────────────────────────────────────────────

    @property
    def is_terminal(self) -> bool:
        """States from which no forward progress is possible."""
        return self in (
            ControlFlowState.EXECUTED,
            ControlFlowState.REJECTED,
            ControlFlowState.BLOCKED,
            ControlFlowState.FROZEN,
            ControlFlowState.CANCELLED,
            ControlFlowState.EXPIRED,
            ControlFlowState.FAILED,
        )

    @property
    def is_error(self) -> bool:
        """States that represent a negative outcome."""
        return self in (
            ControlFlowState.REJECTED,
            ControlFlowState.BLOCKED,
            ControlFlowState.FROZEN,
            ControlFlowState.EXPIRED,
            ControlFlowState.FAILED,
        )

    @property
    def is_active(self) -> bool:
        """States where the flow is still in progress."""
        return not self.is_terminal

    @property
    def label(self) -> str:
        labels = {
            ControlFlowState.PROPOSED: "Proposed",
            ControlFlowState.VALIDATING: "Validating",
            ControlFlowState.RISK_CHECKED: "Risk Checked",
            ControlFlowState.GOVERNANCE_CHECKED: "Governance Checked",
            ControlFlowState.AUTHORIZED: "Authorized",
            ControlFlowState.APPROVED: "Approved",
            ControlFlowState.ORDER_READY: "Order Ready",
            ControlFlowState.SUBMITTED: "Submitted",
            ControlFlowState.EXECUTING: "Executing",
            ControlFlowState.EXECUTED: "Executed",
            ControlFlowState.REJECTED: "Rejected",
            ControlFlowState.BLOCKED: "Blocked",
            ControlFlowState.FROZEN: "Frozen",
            ControlFlowState.CANCELLED: "Cancelled",
            ControlFlowState.EXPIRED: "Expired",
            ControlFlowState.FAILED: "Failed",
        }
        return labels.get(self, "Unknown")


# ── Valid State Transitions ────────────────────────────────────
# Only explicitly listed transitions are allowed.
# Everything else → ValueError.

VALID_CONTROL_TRANSITIONS: Dict[ControlFlowState, List[ControlFlowState]] = {
    ControlFlowState.PROPOSED: [
        ControlFlowState.VALIDATING,
        ControlFlowState.CANCELLED,
    ],
    ControlFlowState.VALIDATING: [
        ControlFlowState.RISK_CHECKED,
        ControlFlowState.REJECTED,
        ControlFlowState.FAILED,
    ],
    ControlFlowState.RISK_CHECKED: [
        ControlFlowState.GOVERNANCE_CHECKED,
        ControlFlowState.REJECTED,
        ControlFlowState.BLOCKED,
    ],
    ControlFlowState.GOVERNANCE_CHECKED: [
        ControlFlowState.AUTHORIZED,
        ControlFlowState.REJECTED,
        ControlFlowState.BLOCKED,
        ControlFlowState.FROZEN,
    ],
    ControlFlowState.AUTHORIZED: [
        ControlFlowState.APPROVED,
        ControlFlowState.REJECTED,
        ControlFlowState.EXPIRED,
    ],
    ControlFlowState.APPROVED: [
        ControlFlowState.ORDER_READY,
        ControlFlowState.EXPIRED,
        ControlFlowState.CANCELLED,
    ],
    ControlFlowState.ORDER_READY: [
        ControlFlowState.SUBMITTED,
        ControlFlowState.CANCELLED,
        ControlFlowState.EXPIRED,
    ],
    ControlFlowState.SUBMITTED: [
        ControlFlowState.EXECUTING,
        ControlFlowState.CANCELLED,
        ControlFlowState.REJECTED,
    ],
    ControlFlowState.EXECUTING: [
        ControlFlowState.EXECUTED,
        ControlFlowState.FAILED,
        ControlFlowState.CANCELLED,
    ],
    # Terminal states have no outgoing transitions
    ControlFlowState.EXECUTED: [],
    ControlFlowState.REJECTED: [],
    ControlFlowState.BLOCKED: [],
    ControlFlowState.FROZEN: [],
    ControlFlowState.CANCELLED: [],
    ControlFlowState.EXPIRED: [],
    ControlFlowState.FAILED: [],
}


def can_transition(from_state: ControlFlowState, to_state: ControlFlowState) -> bool:
    """Check if a state transition is valid."""
    allowed = VALID_CONTROL_TRANSITIONS.get(from_state, [])
    return to_state in allowed


def valid_transitions_from(state: ControlFlowState) -> List[ControlFlowState]:
    """Return list of valid next states."""
    return list(VALID_CONTROL_TRANSITIONS.get(state, []))


def is_fail_closed_state(state: ControlFlowState) -> bool:
    """Check if a state should trigger fail-closed behavior.

    UNKNOWN or indeterminate states must block, not pass.
    """
    return state in (
        ControlFlowState.BLOCKED,
        ControlFlowState.FROZEN,
        ControlFlowState.FAILED,
        ControlFlowState.REJECTED,
    )
