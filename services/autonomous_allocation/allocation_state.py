"""Allocation State — allocation lifecycle states and transitions.

Defines the state machine for allocation lifecycle from inception
through execution to feedback.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AllocationStatus(str, Enum):
    """Allocation lifecycle status."""
    PENDING = "PENDING"
    SCORING = "SCORING"
    RANKED = "RANKED"
    OPTIMIZING = "OPTIMIZING"
    CONSTRAINING = "CONSTRAINING"
    DECIDED = "DECIDED"
    GUARDED = "GUARDED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"
    QUEUED = "QUEUED"
    EXECUTING = "EXECUTING"
    PARTIALLY_EXECUTED = "PARTIALLY_EXECUTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    FEEDBACK = "FEEDBACK"
    ARCHIVED = "ARCHIVED"


VALID_TRANSITIONS: Dict[AllocationStatus, List[AllocationStatus]] = {
    AllocationStatus.PENDING: [AllocationStatus.SCORING],
    AllocationStatus.SCORING: [AllocationStatus.RANKED, AllocationStatus.FAILED],
    AllocationStatus.RANKED: [AllocationStatus.OPTIMIZING, AllocationStatus.REJECTED],
    AllocationStatus.OPTIMIZING: [AllocationStatus.CONSTRAINING, AllocationStatus.FAILED],
    AllocationStatus.CONSTRAINING: [AllocationStatus.DECIDED, AllocationStatus.REJECTED],
    AllocationStatus.DECIDED: [AllocationStatus.GUARDED],
    AllocationStatus.GUARDED: [AllocationStatus.APPROVED, AllocationStatus.REJECTED,
                                AllocationStatus.DEFERRED],
    AllocationStatus.APPROVED: [AllocationStatus.QUEUED],
    AllocationStatus.REJECTED: [AllocationStatus.ARCHIVED],
    AllocationStatus.DEFERRED: [AllocationStatus.PENDING],
    AllocationStatus.QUEUED: [AllocationStatus.EXECUTING],
    AllocationStatus.EXECUTING: [AllocationStatus.COMPLETED, AllocationStatus.PARTIALLY_EXECUTED,
                                  AllocationStatus.FAILED],
    AllocationStatus.PARTIALLY_EXECUTED: [AllocationStatus.EXECUTING, AllocationStatus.COMPLETED,
                                           AllocationStatus.FAILED],
    AllocationStatus.COMPLETED: [AllocationStatus.FEEDBACK],
    AllocationStatus.FAILED: [AllocationStatus.PENDING, AllocationStatus.ARCHIVED],
    AllocationStatus.FEEDBACK: [AllocationStatus.ARCHIVED, AllocationStatus.PENDING],
    AllocationStatus.ARCHIVED: [],
}


@dataclass
class AllocationStateTransition:
    """Record of a state transition."""
    from_status: AllocationStatus
    to_status: AllocationStatus
    timestamp: datetime = field(default_factory=datetime.utcnow)
    reason: str = ""
    actor: str = "SYSTEM"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AllocationState:
    """Tracks the lifecycle state of an allocation."""

    strategy_id: str
    status: AllocationStatus = AllocationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    transitions: List[AllocationStateTransition] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def transition(self, to_status: AllocationStatus,
                   reason: str = "", actor: str = "SYSTEM") -> bool:
        """Attempt a state transition. Returns True if valid."""
        if to_status not in VALID_TRANSITIONS.get(self.status, []):
            return False

        transition_record = AllocationStateTransition(
            from_status=self.status,
            to_status=to_status,
            timestamp=datetime.utcnow(),
            reason=reason,
            actor=actor,
        )
        self.transitions.append(transition_record)
        self.status = to_status
        self.updated_at = datetime.utcnow()
        return True

    def can_transition_to(self, target: AllocationStatus) -> bool:
        """Check if a transition is valid."""
        return target in VALID_TRANSITIONS.get(self.status, [])

    def get_available_transitions(self) -> List[AllocationStatus]:
        """Get list of valid next states."""
        return VALID_TRANSITIONS.get(self.status, [])

    def time_in_state(self) -> float:
        """Seconds spent in current state."""
        return (datetime.utcnow() - self.updated_at).total_seconds()

    def total_time(self) -> float:
        """Total seconds since creation."""
        return (datetime.utcnow() - self.created_at).total_seconds()

    def is_terminal(self) -> bool:
        """Check if in a terminal state."""
        return self.status in (AllocationStatus.ARCHIVED,)

    def is_active(self) -> bool:
        """Check if in an active processing state."""
        return self.status in (
            AllocationStatus.SCORING, AllocationStatus.OPTIMIZING,
            AllocationStatus.CONSTRAINING, AllocationStatus.GUARDED,
            AllocationStatus.EXECUTING, AllocationStatus.PARTIALLY_EXECUTED,
        )

    def is_completed(self) -> bool:
        """Check if allocation has completed."""
        return self.status in (
            AllocationStatus.COMPLETED, AllocationStatus.FEEDBACK,
            AllocationStatus.ARCHIVED,
        )

    def history(self) -> List[Dict[str, Any]]:
        """Get full state transition history."""
        return [
            {
                "from": t.from_status.value,
                "to": t.to_status.value,
                "timestamp": t.timestamp.isoformat(),
                "reason": t.reason,
                "actor": t.actor,
            }
            for t in self.transitions
        ]
