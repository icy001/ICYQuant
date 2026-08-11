"""
Control Transition — auditable record of every state change in the control flow.

Commit 21 Part 1.1: each transition is recorded with actor, reason, version
pinning, and correlation data for full audit traceability.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .control_state import ControlFlowState, can_transition


@dataclass
class ControlTransition:
    """Record of a single state change in the control flow.

    Example:
        flow_id:      FLOW-001
        from_state:   RISK_CHECKED
        to_state:     GOVERNANCE_CHECKED
        actor:        governance-control-plane
        reason:       policy_pass
        policy_version: POLICY-v7
        timestamp:    ...
    """

    # ── Identity ───────────────────────────────────────────────
    transition_id: str = field(default_factory=lambda: f"CT-{uuid.uuid4().hex[:12].upper()}")

    # ── State Change ───────────────────────────────────────────
    from_state: ControlFlowState = ControlFlowState.PROPOSED
    to_state: ControlFlowState = ControlFlowState.PROPOSED

    # ── Context ────────────────────────────────────────────────
    flow_id: str = ""
    decision_id: str = ""
    actor: str = ""
    reason: str = ""

    # ── Version Pinning ────────────────────────────────────────
    policy_version: str = ""
    risk_version: str = ""
    governance_version: str = ""

    # ── Metadata ───────────────────────────────────────────────
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ── Validation ─────────────────────────────────────────────

    def __post_init__(self):
        if not can_transition(self.from_state, self.to_state):
            raise ValueError(
                f"Invalid control transition: {self.from_state.name} → {self.to_state.name}"
            )

    # ── Properties ─────────────────────────────────────────────

    @property
    def is_terminal(self) -> bool:
        """Whether this transition ends the flow."""
        return self.to_state.is_terminal

    @property
    def is_error_transition(self) -> bool:
        """Whether this transition moves to an error state."""
        return self.to_state.is_error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "from_state": self.from_state.name,
            "to_state": self.to_state.name,
            "flow_id": self.flow_id,
            "decision_id": self.decision_id,
            "actor": self.actor,
            "reason": self.reason,
            "policy_version": self.policy_version,
            "risk_version": self.risk_version,
            "governance_version": self.governance_version,
            "timestamp": self.timestamp,
            "is_terminal": self.is_terminal,
            "is_error": self.is_error_transition,
            "metadata": self.metadata,
        }
