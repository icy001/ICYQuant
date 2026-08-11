"""
Policy Status — lifecycle and version status enums with state machine.

Policy lifecycle:
  DRAFT → VALIDATED → APPROVED → PUBLISHED → ACTIVE → SUPERSEDED → ARCHIVED
  Exceptions: REJECTED, REVOKED, EXPIRED
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, FrozenSet, Optional, Set


class PolicyLifecycleStatus(Enum):
    """
    Full lifecycle status for a policy version.

    Normal flow: DRAFT → VALIDATED → APPROVED → PUBLISHED → ACTIVE → SUPERSEDED → ARCHIVED
    Terminal/error: REJECTED (from VALIDATED or APPROVED)
                    REVOKED (from PUBLISHED or ACTIVE)
                    EXPIRED (from ACTIVE)
    """

    DRAFT = auto()
    VALIDATED = auto()
    APPROVED = auto()
    PUBLISHED = auto()
    ACTIVE = auto()
    SUPERSEDED = auto()
    ARCHIVED = auto()

    # Exceptional states
    REJECTED = auto()
    REVOKED = auto()
    EXPIRED = auto()

    @property
    def is_active(self) -> bool:
        """Whether this status represents an active (enforceable) policy."""
        return self in (PolicyLifecycleStatus.ACTIVE,)

    @property
    def is_terminal(self) -> bool:
        """Whether this is a terminal state (no further transitions)."""
        return self in (
            PolicyLifecycleStatus.ARCHIVED,
            PolicyLifecycleStatus.REJECTED,
            PolicyLifecycleStatus.REVOKED,
            PolicyLifecycleStatus.EXPIRED,
        )

    @property
    def is_editable(self) -> bool:
        """Whether the policy can be modified in this status."""
        return self in (
            PolicyLifecycleStatus.DRAFT,
            PolicyLifecycleStatus.VALIDATED,
        )

    @property
    def is_publishable(self) -> bool:
        """Whether the policy can be published from this status."""
        return self in (
            PolicyLifecycleStatus.APPROVED,
        )

    @property
    def is_in_effect(self) -> bool:
        """Whether this policy version is currently in effect."""
        return self == PolicyLifecycleStatus.ACTIVE

    @property
    def display_name(self) -> str:
        names = {
            PolicyLifecycleStatus.DRAFT: "Draft",
            PolicyLifecycleStatus.VALIDATED: "Validated",
            PolicyLifecycleStatus.APPROVED: "Approved",
            PolicyLifecycleStatus.PUBLISHED: "Published",
            PolicyLifecycleStatus.ACTIVE: "Active",
            PolicyLifecycleStatus.SUPERSEDED: "Superseded",
            PolicyLifecycleStatus.ARCHIVED: "Archived",
            PolicyLifecycleStatus.REJECTED: "Rejected",
            PolicyLifecycleStatus.REVOKED: "Revoked",
            PolicyLifecycleStatus.EXPIRED: "Expired",
        }
        return names.get(self, self.name)


class VersionStatus(Enum):
    """Simplified version status for internal tracking."""

    CURRENT = auto()       # Currently active version
    PREVIOUS = auto()      # Previous version (still valid but not active)
    SUPERSEDED = auto()    # Superseded by a newer version
    DEPRECATED = auto()    # Marked for removal
    WITHDRAWN = auto()     # Withdrawn without replacement


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

class PolicyStateMachine:
    """
    Validates transitions in the policy lifecycle state machine.

    Normal flow:
      DRAFT → VALIDATED → APPROVED → PUBLISHED → ACTIVE → SUPERSEDED → ARCHIVED

    Allowed shortcuts:
      DRAFT → REJECTED       (reject during drafting)
      VALIDATED → REJECTED   (reject after validation)
      VALIDATED → DRAFT      (send back for revision)
      APPROVED → REJECTED    (reject after approval)
      APPROVED → DRAFT       (send back for revision)
      PUBLISHED → REVOKED    (revoke a published version)
      ACTIVE → REVOKED       (revoke an active version)
      ACTIVE → EXPIRED       (version expired)
      REVOKED → ARCHIVED     (archive revoked versions)
      EXPIRED → ARCHIVED     (archive expired versions)
    """

    # Valid transitions: source -> allowed targets
    VALID_TRANSITIONS: Dict[PolicyLifecycleStatus, FrozenSet[PolicyLifecycleStatus]] = {
        PolicyLifecycleStatus.DRAFT: frozenset({
            PolicyLifecycleStatus.VALIDATED,
            PolicyLifecycleStatus.REJECTED,
        }),
        PolicyLifecycleStatus.VALIDATED: frozenset({
            PolicyLifecycleStatus.APPROVED,
            PolicyLifecycleStatus.DRAFT,
            PolicyLifecycleStatus.REJECTED,
        }),
        PolicyLifecycleStatus.APPROVED: frozenset({
            PolicyLifecycleStatus.PUBLISHED,
            PolicyLifecycleStatus.DRAFT,
            PolicyLifecycleStatus.REJECTED,
        }),
        PolicyLifecycleStatus.PUBLISHED: frozenset({
            PolicyLifecycleStatus.ACTIVE,
            PolicyLifecycleStatus.REVOKED,
        }),
        PolicyLifecycleStatus.ACTIVE: frozenset({
            PolicyLifecycleStatus.SUPERSEDED,
            PolicyLifecycleStatus.REVOKED,
            PolicyLifecycleStatus.EXPIRED,
        }),
        PolicyLifecycleStatus.SUPERSEDED: frozenset({
            PolicyLifecycleStatus.ARCHIVED,
        }),
        PolicyLifecycleStatus.REVOKED: frozenset({
            PolicyLifecycleStatus.ARCHIVED,
        }),
        PolicyLifecycleStatus.EXPIRED: frozenset({
            PolicyLifecycleStatus.ARCHIVED,
        }),
        PolicyLifecycleStatus.ARCHIVED: frozenset(),
        PolicyLifecycleStatus.REJECTED: frozenset(),
    }

    @classmethod
    def can_transition(
        cls,
        from_status: PolicyLifecycleStatus,
        to_status: PolicyLifecycleStatus,
    ) -> bool:
        """Check if a transition is valid."""
        allowed = cls.VALID_TRANSITIONS.get(from_status, frozenset())
        return to_status in allowed

    @classmethod
    def validate_transition(
        cls,
        from_status: PolicyLifecycleStatus,
        to_status: PolicyLifecycleStatus,
    ) -> None:
        """Raise ValueError if transition is invalid."""
        if not cls.can_transition(from_status, to_status):
            raise ValueError(
                f"Invalid policy lifecycle transition: "
                f"{from_status.name} → {to_status.name}"
            )

    @classmethod
    def allowed_transitions(
        cls, from_status: PolicyLifecycleStatus
    ) -> FrozenSet[PolicyLifecycleStatus]:
        """Return all valid next states."""
        return cls.VALID_TRANSITIONS.get(from_status, frozenset())

    @classmethod
    def get_transition_path(
        cls,
        from_status: PolicyLifecycleStatus,
        to_status: PolicyLifecycleStatus,
    ) -> Optional[str]:
        """Get a human-readable description of the transition path."""
        if not cls.can_transition(from_status, to_status):
            return None

        descriptions = {
            (PolicyLifecycleStatus.DRAFT, PolicyLifecycleStatus.VALIDATED): "Draft validated",
            (PolicyLifecycleStatus.DRAFT, PolicyLifecycleStatus.REJECTED): "Draft rejected",
            (PolicyLifecycleStatus.VALIDATED, PolicyLifecycleStatus.APPROVED): "Policy approved",
            (PolicyLifecycleStatus.VALIDATED, PolicyLifecycleStatus.DRAFT): "Sent back to draft",
            (PolicyLifecycleStatus.VALIDATED, PolicyLifecycleStatus.REJECTED): "Policy rejected",
            (PolicyLifecycleStatus.APPROVED, PolicyLifecycleStatus.PUBLISHED): "Policy published",
            (PolicyLifecycleStatus.APPROVED, PolicyLifecycleStatus.DRAFT): "Sent back to draft",
            (PolicyLifecycleStatus.APPROVED, PolicyLifecycleStatus.REJECTED): "Policy rejected",
            (PolicyLifecycleStatus.PUBLISHED, PolicyLifecycleStatus.ACTIVE): "Policy activated",
            (PolicyLifecycleStatus.PUBLISHED, PolicyLifecycleStatus.REVOKED): "Policy revoked",
            (PolicyLifecycleStatus.ACTIVE, PolicyLifecycleStatus.SUPERSEDED): "Policy superseded",
            (PolicyLifecycleStatus.ACTIVE, PolicyLifecycleStatus.REVOKED): "Policy revoked",
            (PolicyLifecycleStatus.ACTIVE, PolicyLifecycleStatus.EXPIRED): "Policy expired",
            (PolicyLifecycleStatus.SUPERSEDED, PolicyLifecycleStatus.ARCHIVED): "Archived",
            (PolicyLifecycleStatus.REVOKED, PolicyLifecycleStatus.ARCHIVED): "Archived",
            (PolicyLifecycleStatus.EXPIRED, PolicyLifecycleStatus.ARCHIVED): "Archived",
        }
        return descriptions.get((from_status, to_status))
