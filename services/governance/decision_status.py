"""
Decision Status — the state machine for governance decisions.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Dict, List, Optional, Set


class DecisionStatus(Enum):
    """Lifecycle states of a governance decision."""

    REQUESTED = auto()
    EVALUATING = auto()
    POLICY_EVALUATED = auto()
    AUTHORITY_EVALUATED = auto()
    CONSTRAINTS_EVALUATED = auto()
    APPROVAL_PENDING = auto()
    APPROVED = auto()
    REJECTED = auto()
    ALLOWED = auto()
    BLOCKED = auto()
    OVERRIDDEN = auto()
    EXPIRED = auto()
    CANCELLED = auto()
    EXECUTABLE = auto()
    EXECUTED = auto()
    ERROR = auto()


# Valid transitions
_VALID_TRANSITIONS: Dict[DecisionStatus, Set[DecisionStatus]] = {
    DecisionStatus.REQUESTED: {
        DecisionStatus.EVALUATING,
        DecisionStatus.CANCELLED,
        DecisionStatus.EXPIRED,
    },
    DecisionStatus.EVALUATING: {
        DecisionStatus.POLICY_EVALUATED,
        DecisionStatus.BLOCKED,
        DecisionStatus.ERROR,
    },
    DecisionStatus.POLICY_EVALUATED: {
        DecisionStatus.AUTHORITY_EVALUATED,
        DecisionStatus.BLOCKED,
        DecisionStatus.ERROR,
    },
    DecisionStatus.AUTHORITY_EVALUATED: {
        DecisionStatus.CONSTRAINTS_EVALUATED,
        DecisionStatus.BLOCKED,
        DecisionStatus.ERROR,
    },
    DecisionStatus.CONSTRAINTS_EVALUATED: {
        DecisionStatus.APPROVAL_PENDING,
        DecisionStatus.ALLOWED,
        DecisionStatus.BLOCKED,
        DecisionStatus.ERROR,
    },
    DecisionStatus.APPROVAL_PENDING: {
        DecisionStatus.APPROVED,
        DecisionStatus.REJECTED,
        DecisionStatus.EXPIRED,
    },
    DecisionStatus.APPROVED: {
        DecisionStatus.EXECUTABLE,
        DecisionStatus.OVERRIDDEN,
    },
    DecisionStatus.REJECTED: set(),
    DecisionStatus.ALLOWED: {
        DecisionStatus.EXECUTABLE,
        DecisionStatus.OVERRIDDEN,
    },
    DecisionStatus.BLOCKED: {
        DecisionStatus.OVERRIDDEN,
        DecisionStatus.CANCELLED,
    },
    DecisionStatus.OVERRIDDEN: {
        DecisionStatus.EXECUTABLE,
        DecisionStatus.ALLOWED,
    },
    DecisionStatus.EXECUTABLE: {
        DecisionStatus.EXECUTED,
        DecisionStatus.CANCELLED,
    },
    DecisionStatus.EXECUTED: set(),
    DecisionStatus.EXPIRED: set(),
    DecisionStatus.CANCELLED: set(),
    DecisionStatus.ERROR: {
        DecisionStatus.REQUESTED,  # retry
        DecisionStatus.CANCELLED,
    },
}

# Terminal states
TERMINAL_STATUSES: Set[DecisionStatus] = {
    DecisionStatus.REJECTED,
    DecisionStatus.BLOCKED,
    DecisionStatus.EXECUTED,
    DecisionStatus.EXPIRED,
    DecisionStatus.CANCELLED,
}


def can_transition(from_status: DecisionStatus, to_status: DecisionStatus) -> bool:
    """Check if a status transition is valid."""
    allowed = _VALID_TRANSITIONS.get(from_status, set())
    return to_status in allowed


def is_terminal(status: DecisionStatus) -> bool:
    """Check if a status is terminal (no further transitions)."""
    return status in TERMINAL_STATUSES


def is_success(status: DecisionStatus) -> bool:
    """Check if a status represents a successful outcome."""
    return status in {DecisionStatus.ALLOWED, DecisionStatus.EXECUTABLE, DecisionStatus.EXECUTED}


class DecisionStateMachine:
    """Tracks the lifecycle state of a single governance decision."""

    def __init__(self, decision_id: str):
        self.decision_id = decision_id
        self._status: DecisionStatus = DecisionStatus.REQUESTED
        self._history: List[DecisionStatus] = [DecisionStatus.REQUESTED]

    @property
    def status(self) -> DecisionStatus:
        return self._status

    @property
    def is_terminal(self) -> bool:
        return is_terminal(self._status)

    @property
    def is_success(self) -> bool:
        return is_success(self._status)

    def transition(self, to_status: DecisionStatus) -> bool:
        """Attempt a state transition. Returns True if valid."""
        if not can_transition(self._status, to_status):
            return False
        self._status = to_status
        self._history.append(to_status)
        return True

    def force_transition(self, to_status: DecisionStatus) -> None:
        """Force a transition regardless of validity (use with caution)."""
        self._status = to_status
        self._history.append(to_status)

    def get_history(self) -> List[str]:
        return [s.name for s in self._history]
