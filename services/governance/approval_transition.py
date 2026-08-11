"""
Approval Transition — validates state transitions in the approval lifecycle.

Ensures that approval moves through valid states only:
  DRAFT → SUBMITTED → PENDING → UNDER_REVIEW → APPROVED → EXECUTABLE → EXECUTED
with error paths: REJECTED, EXPIRED, CANCELLED, REVOKED, SUPERSEDED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Optional

from .approval_status import ApprovalStatus


# Valid transitions
_VALID_TRANSITIONS: Dict[ApprovalStatus, FrozenSet[ApprovalStatus]] = {
    ApprovalStatus.DRAFT: frozenset({
        ApprovalStatus.SUBMITTED,
        ApprovalStatus.CANCELLED,
    }),
    ApprovalStatus.SUBMITTED: frozenset({
        ApprovalStatus.PENDING,
        ApprovalStatus.CANCELLED,
        ApprovalStatus.REJECTED,
    }),
    ApprovalStatus.PENDING: frozenset({
        ApprovalStatus.UNDER_REVIEW,
        ApprovalStatus.CANCELLED,
        ApprovalStatus.EXPIRED,
    }),
    ApprovalStatus.UNDER_REVIEW: frozenset({
        ApprovalStatus.APPROVED,
        ApprovalStatus.REJECTED,
        ApprovalStatus.CANCELLED,
        ApprovalStatus.EXPIRED,
    }),
    ApprovalStatus.APPROVED: frozenset({
        ApprovalStatus.EXECUTABLE,
        ApprovalStatus.REVOKED,
        ApprovalStatus.INVALIDATED,
        ApprovalStatus.EXPIRED,
    }),
    ApprovalStatus.EXECUTABLE: frozenset({
        ApprovalStatus.EXECUTED,
        ApprovalStatus.REVOKED,
        ApprovalStatus.INVALIDATED,
    }),
    ApprovalStatus.EXECUTED: frozenset(),  # Terminal
    ApprovalStatus.REJECTED: frozenset({
        ApprovalStatus.SUPERSEDED,
    }),
    ApprovalStatus.EXPIRED: frozenset({
        ApprovalStatus.SUPERSEDED,
    }),
    ApprovalStatus.CANCELLED: frozenset({
        ApprovalStatus.SUPERSEDED,
    }),
    ApprovalStatus.REVOKED: frozenset({
        ApprovalStatus.SUPERSEDED,
    }),
    ApprovalStatus.INVALIDATED: frozenset({
        ApprovalStatus.SUPERSEDED,
    }),
    ApprovalStatus.SUPERSEDED: frozenset(),  # Terminal
}


# Terminal states — cannot transition further
_TERMINAL_STATES: FrozenSet[ApprovalStatus] = frozenset({
    ApprovalStatus.EXECUTED,
    ApprovalStatus.SUPERSEDED,
})


@dataclass
class ApprovalTransition:
    """Represents a state transition within the approval lifecycle."""

    approval_id: str
    from_status: ApprovalStatus
    to_status: ApprovalStatus
    reason: str = ""
    actor: str = "SYSTEM"
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        """Check if this transition is valid according to the state machine."""
        allowed = _VALID_TRANSITIONS.get(self.from_status, frozenset())
        return self.to_status in allowed

    def is_terminal(self) -> bool:
        """Check if the destination is a terminal state."""
        return self.to_status in _TERMINAL_STATES

    @classmethod
    def can_transition(cls, from_status: ApprovalStatus, to_status: ApprovalStatus) -> bool:
        """Check if a transition from one status to another is valid."""
        allowed = _VALID_TRANSITIONS.get(from_status, frozenset())
        return to_status in allowed

    @classmethod
    def valid_transitions_from(cls, status: ApprovalStatus) -> FrozenSet[ApprovalStatus]:
        """Get all valid next statuses from a given status."""
        return _VALID_TRANSITIONS.get(status, frozenset())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "from_status": self.from_status.name,
            "to_status": self.to_status.name,
            "reason": self.reason,
            "actor": self.actor,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
