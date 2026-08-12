"""
IncidentStatus — lifecycle state of an incident.

Happy path:
    OPEN → ACKNOWLEDGED → MITIGATING → RESOLVED

Exception path:
    OPEN → ESCALATED → MITIGATING → RESOLVED

Reoccurrence:
    RESOLVED → REOPENED

An incident never disappears because of one wrong close (spec section 6, 18).
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Set


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    """Detected but not yet acknowledged."""

    ACKNOWLEDGED = "ACKNOWLEDGED"
    """Known — but acknowledging is NOT resolving (spec section 31)."""

    MITIGATING = "MITIGATING"
    """Mitigation / recovery in progress."""

    RESOLVED = "RESOLVED"
    """Closed with a resolution reason + verification."""

    ESCALATED = "ESCALATED"
    """Raised — recovery failed or severity increased."""

    REOPENED = "REOPENED"
    """A previously resolved incident reappeared."""

    CLOSED = "CLOSED"
    """Resolution verified by the system; the incident is permanently closed.

    CLOSED is the terminal state: RESOLVED means handling finished, CLOSED
    means the system verified the problem is stable (spec section 1.3).
    """

    @property
    def is_open(self) -> bool:
        return self not in (
            IncidentStatus.RESOLVED,
            IncidentStatus.CLOSED,
        )

    @property
    def is_resolved(self) -> bool:
        return self is IncidentStatus.RESOLVED


class IncidentStateTransitionError(Exception):
    """Raised when an incident status transition is rejected."""

    def __init__(self, from_state: IncidentStatus, to_state: IncidentStatus) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Invalid incident state transition: {from_state.value} -> {to_state.value}"
        )


class IncidentStateMachine:
    """Allowed incident status transitions (spec section 18)."""

    ALLOWED_TRANSITIONS: Dict[IncidentStatus, Set[IncidentStatus]] = {
        IncidentStatus.OPEN: {
            IncidentStatus.ACKNOWLEDGED,
            IncidentStatus.MITIGATING,
            IncidentStatus.ESCALATED,
        },
        IncidentStatus.ACKNOWLEDGED: {
            IncidentStatus.MITIGATING,
            IncidentStatus.ESCALATED,
            IncidentStatus.RESOLVED,
        },
        IncidentStatus.MITIGATING: {
            IncidentStatus.RESOLVED,
            IncidentStatus.ESCALATED,
        },
        IncidentStatus.ESCALATED: {
            IncidentStatus.MITIGATING,
            IncidentStatus.RESOLVED,
        },
        IncidentStatus.RESOLVED: {
            IncidentStatus.REOPENED,
        },
        IncidentStatus.REOPENED: {
            IncidentStatus.ACKNOWLEDGED,
            IncidentStatus.MITIGATING,
            IncidentStatus.ESCALATED,
            IncidentStatus.RESOLVED,
        },
    }

    @classmethod
    def can_transition(
        cls, from_state: IncidentStatus, to_state: IncidentStatus
    ) -> bool:
        return to_state in cls.ALLOWED_TRANSITIONS.get(from_state, set())

    @classmethod
    def assert_transition(
        cls, from_state: IncidentStatus, to_state: IncidentStatus
    ) -> None:
        if not cls.can_transition(from_state, to_state):
            raise IncidentStateTransitionError(from_state, to_state)
