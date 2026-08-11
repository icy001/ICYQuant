"""
Delegation Status — lifecycle states for authority delegations.

Delegations follow: CREATED → ACTIVE → EXPIRED / REVOKED
with strict controls on lifetime and sub-delegation.
"""

from __future__ import annotations

from enum import Enum, auto


class DelegationStatus(Enum):
    """Lifecycle states for an authority delegation."""

    DRAFT = auto()         # Being set up, not yet active
    ACTIVE = auto()        # Currently active delegation
    EXPIRED = auto()       # Past valid_to
    REVOKED = auto()       # Explicitly revoked by delegator
    SUPERSEDED = auto()    # Replaced by a newer delegation
    INVALID = auto()       # Invalid (e.g., scope/limit violation)


# Non-reversible statuses
_ACTIVEABLE: frozenset = frozenset({DelegationStatus.DRAFT})
_TERMINAL: frozenset = frozenset({
    DelegationStatus.EXPIRED,
    DelegationStatus.REVOKED,
    DelegationStatus.SUPERSEDED,
    DelegationStatus.INVALID,
})


def can_activate(status: DelegationStatus) -> bool:
    """Check if a delegation can be activated from this status."""
    return status in _ACTIVEABLE


def is_terminal(status: DelegationStatus) -> bool:
    """Check if this status is terminal (cannot change)."""
    return status in _TERMINAL
