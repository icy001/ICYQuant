"""
Approval Status — full lifecycle state machine for approval requests.

States: DRAFT → SUBMITTED → PENDING → UNDER_REVIEW → APPROVED → EXECUTABLE → EXECUTED
Exceptions: REJECTED, EXPIRED, CANCELLED, REVOKED, SUPERSEDED
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, FrozenSet, List, Optional


class ApprovalStatus(Enum):
    """Complete approval lifecycle status."""

    DRAFT = auto()
    SUBMITTED = auto()
    PENDING = auto()
    UNDER_REVIEW = auto()
    APPROVED = auto()
    EXECUTABLE = auto()
    EXECUTED = auto()

    # Terminal / exception states
    REJECTED = auto()
    EXPIRED = auto()
    CANCELLED = auto()
    REVOKED = auto()
    SUPERSEDED = auto()
    INVALIDATED = auto()  # Material change detected post-approval

    @property
    def is_active(self) -> bool:
        """Is the request still in-progress?"""
        return self in (
            ApprovalStatus.SUBMITTED,
            ApprovalStatus.PENDING,
            ApprovalStatus.UNDER_REVIEW,
        )

    @property
    def is_terminal(self) -> bool:
        """Has the request reached a terminal state?"""
        return self in (
            ApprovalStatus.EXECUTED,
            ApprovalStatus.REJECTED,
            ApprovalStatus.EXPIRED,
            ApprovalStatus.CANCELLED,
            ApprovalStatus.REVOKED,
            ApprovalStatus.SUPERSEDED,
            ApprovalStatus.INVALIDATED,
        )

    @property
    def is_editable(self) -> bool:
        """Can the request still be modified?"""
        return self in (ApprovalStatus.DRAFT,)

    @property
    def is_effective(self) -> bool:
        """Does this status represent a valid approval?"""
        return self in (ApprovalStatus.APPROVED, ApprovalStatus.EXECUTABLE)

    @property
    def is_consumed(self) -> bool:
        """Has the approval been used?"""
        return self == ApprovalStatus.EXECUTED


class ApprovalStateMachine:
    """Validates transitions between approval statuses."""

    VALID_TRANSITIONS: Dict[ApprovalStatus, FrozenSet[ApprovalStatus]] = {
        ApprovalStatus.DRAFT: frozenset({
            ApprovalStatus.SUBMITTED,
            ApprovalStatus.CANCELLED,
        }),
        ApprovalStatus.SUBMITTED: frozenset({
            ApprovalStatus.PENDING,
            ApprovalStatus.REJECTED,
            ApprovalStatus.CANCELLED,
        }),
        ApprovalStatus.PENDING: frozenset({
            ApprovalStatus.UNDER_REVIEW,
            ApprovalStatus.REJECTED,
            ApprovalStatus.EXPIRED,
            ApprovalStatus.CANCELLED,
        }),
        ApprovalStatus.UNDER_REVIEW: frozenset({
            ApprovalStatus.APPROVED,
            ApprovalStatus.REJECTED,
            ApprovalStatus.EXPIRED,
            ApprovalStatus.CANCELLED,
        }),
        ApprovalStatus.APPROVED: frozenset({
            ApprovalStatus.EXECUTABLE,
            ApprovalStatus.REVOKED,
            ApprovalStatus.EXPIRED,
            ApprovalStatus.SUPERSEDED,
            ApprovalStatus.INVALIDATED,
        }),
        ApprovalStatus.EXECUTABLE: frozenset({
            ApprovalStatus.EXECUTED,
            ApprovalStatus.REVOKED,
            ApprovalStatus.EXPIRED,
            ApprovalStatus.INVALIDATED,
        }),
        ApprovalStatus.EXECUTED: frozenset(),
        # Terminal states — cannot leave
        ApprovalStatus.REJECTED: frozenset(),
        ApprovalStatus.EXPIRED: frozenset(),
        ApprovalStatus.CANCELLED: frozenset(),
        ApprovalStatus.REVOKED: frozenset(),
        ApprovalStatus.SUPERSEDED: frozenset(),
        ApprovalStatus.INVALIDATED: frozenset(),
    }

    @classmethod
    def can_transition(cls, current: ApprovalStatus, target: ApprovalStatus) -> bool:
        """Check if a transition is valid."""
        allowed = cls.VALID_TRANSITIONS.get(current, frozenset())
        return target in allowed

    @classmethod
    def validate_transition(cls, current: ApprovalStatus, target: ApprovalStatus) -> None:
        """Raise ValueError if transition is invalid."""
        if not cls.can_transition(current, target):
            allowed = cls.allowed_transitions(current)
            raise ValueError(
                f"Cannot transition from {current.name} to {target.name}. "
                f"Allowed: {[s.name for s in allowed]}"
            )

    @classmethod
    def allowed_transitions(cls, current: ApprovalStatus) -> List[ApprovalStatus]:
        return sorted(cls.VALID_TRANSITIONS.get(current, frozenset()), key=lambda s: s.name)
