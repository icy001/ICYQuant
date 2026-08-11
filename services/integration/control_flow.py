"""
Control Flow — state machine that governs the institutional trading lifecycle.

Commit 21 Part 1.1: every trade must pass through this state machine.
No gate can be bypassed. Unknown state fails closed.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .control_state import ControlFlowState, can_transition, valid_transitions_from
from .control_transition import ControlTransition
from .control_context import TradingControlContext
from .control_result import ControlResult, GateStatus


@dataclass
class ControlFlow:
    """State machine governing the full institutional trading control lifecycle.

    Enforces:
      - Valid state transitions only
      - No gate bypassing
      - Fail-closed on unknown state
      - Full audit trail via transition records
    """

    flow_id: str = field(default_factory=lambda: f"FLOW-{uuid.uuid4().hex[:12].upper()}")
    context: TradingControlContext = field(default_factory=TradingControlContext)

    # ── Runtime State ──────────────────────────────────────────
    _current_state: ControlFlowState = ControlFlowState.PROPOSED
    _transitions: List[ControlTransition] = field(default_factory=list)
    _gate_results: Dict[str, ControlResult] = field(default_factory=dict)

    # ── Lock ───────────────────────────────────────────────────
    _idempotency_keys: set = field(default_factory=set)

    def __post_init__(self):
        # Always sync context flow_id to the control flow's flow_id.
        # Both may have auto-generated IDs, so we overwrite context's.
        self.context.flow_id = self.flow_id

    # ── State Properties ───────────────────────────────────────

    @property
    def current_state(self) -> ControlFlowState:
        return self._current_state

    @property
    def is_terminal(self) -> bool:
        return self._current_state.is_terminal

    @property
    def is_active(self) -> bool:
        return self._current_state.is_active

    @property
    def transitions(self) -> List[ControlTransition]:
        return list(self._transitions)

    # ── Transition ─────────────────────────────────────────────

    def transition(
        self,
        to_state: ControlFlowState,
        reason: str = "",
        actor: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ControlTransition:
        """Execute a validated state transition.

        Raises:
            ValueError: if transition is not valid.
        """
        if not can_transition(self._current_state, to_state):
            raise ValueError(
                f"Invalid control transition: {self._current_state.name} → {to_state.name}"
            )

        t = ControlTransition(
            from_state=self._current_state,
            to_state=to_state,
            flow_id=self.flow_id,
            decision_id=self.context.decision_id or "",
            actor=actor,
            reason=reason,
            policy_version=self.context.policy_version or "",
            risk_version=self.context.risk_version or "",
            governance_version=self.context.governance_version or "",
            metadata=metadata or {},
        )

        self._current_state = to_state
        self._transitions.append(t)
        self.context.touch()

        return t

    # ── Idempotency ────────────────────────────────────────────

    def ensure_idempotent(self, key: str) -> bool:
        """Check and register an idempotency key.

        Returns True if this is the first time seeing this key.
        Returns False if already processed (duplicate).
        """
        if key in self._idempotency_keys:
            return False
        self._idempotency_keys.add(key)
        return True

    def is_duplicate(self, key: str) -> bool:
        """Check if an idempotency key has already been processed."""
        return key in self._idempotency_keys

    # ── Gate Results ───────────────────────────────────────────

    def record_gate_result(self, gate_name: str, result: ControlResult) -> None:
        """Record the result of a gate evaluation."""
        self._gate_results[gate_name] = result

    def get_gate_result(self, gate_name: str) -> Optional[ControlResult]:
        """Get a previously recorded gate result."""
        return self._gate_results.get(gate_name)

    # ── Convenience Transitions ────────────────────────────────

    def advance_to_validating(self, reason: str = "", actor: str = "") -> ControlTransition:
        return self.transition(ControlFlowState.VALIDATING, reason=reason, actor=actor)

    def advance_to_risk_checked(self, reason: str = "", actor: str = "") -> ControlTransition:
        return self.transition(ControlFlowState.RISK_CHECKED, reason=reason, actor=actor)

    def advance_to_governance_checked(self, reason: str = "", actor: str = "") -> ControlTransition:
        return self.transition(ControlFlowState.GOVERNANCE_CHECKED, reason=reason, actor=actor)

    def advance_to_authorized(self, reason: str = "", actor: str = "") -> ControlTransition:
        return self.transition(ControlFlowState.AUTHORIZED, reason=reason, actor=actor)

    def advance_to_approved(self, reason: str = "", actor: str = "") -> ControlTransition:
        return self.transition(ControlFlowState.APPROVED, reason=reason, actor=actor)

    def advance_to_order_ready(self, reason: str = "", actor: str = "") -> ControlTransition:
        return self.transition(ControlFlowState.ORDER_READY, reason=reason, actor=actor)

    def advance_to_submitted(self, reason: str = "", actor: str = "") -> ControlTransition:
        return self.transition(ControlFlowState.SUBMITTED, reason=reason, actor=actor)

    def advance_to_executing(self, reason: str = "", actor: str = "") -> ControlTransition:
        return self.transition(ControlFlowState.EXECUTING, reason=reason, actor=actor)

    def advance_to_executed(self, reason: str = "", actor: str = "") -> ControlTransition:
        return self.transition(ControlFlowState.EXECUTED, reason=reason, actor=actor)

    def reject(self, reason: str = "", actor: str = "") -> ControlTransition:
        return self.transition(ControlFlowState.REJECTED, reason=reason, actor=actor)

    def block(self, reason: str = "", actor: str = "") -> ControlTransition:
        return self.transition(ControlFlowState.BLOCKED, reason=reason, actor=actor)

    def freeze(self, reason: str = "", actor: str = "") -> ControlTransition:
        return self.transition(ControlFlowState.FROZEN, reason=reason, actor=actor)

    def cancel(self, reason: str = "", actor: str = "") -> ControlTransition:
        return self.transition(ControlFlowState.CANCELLED, reason=reason, actor=actor)

    def expire(self, reason: str = "", actor: str = "") -> ControlTransition:
        return self.transition(ControlFlowState.EXPIRED, reason=reason, actor=actor)

    def fail(self, reason: str = "", actor: str = "") -> ControlTransition:
        return self.transition(ControlFlowState.FAILED, reason=reason, actor=actor)

    # ── Summary ────────────────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "current_state": self._current_state.name,
            "is_active": self.is_active,
            "is_terminal": self.is_terminal,
            "transition_count": len(self._transitions),
            "gate_results": {k: v.status.name for k, v in self._gate_results.items()},
            "context": self.context.to_dict(),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.summary(),
            "transitions": [t.to_dict() for t in self._transitions],
        }
