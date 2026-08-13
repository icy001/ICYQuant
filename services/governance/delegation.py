"""
Delegation — represents a transfer of authority from delegator to delegate.

Core security constraints:
  1. Delegation authority <= Original authority (all dimensions)
  2. Delegation depth defaults to 1 (no chain delegation)
  3. Sub-delegation requires explicit opt-in
  4. Cannot expand scope, amount, risk, actions, or duration
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .delegation_status import DelegationStatus
from .delegation_scope import DelegationScope
from .delegation_limit import DelegationLimit
from .authority_grant import AuthorityGrant


@dataclass
class Delegation:
    """
    A transfer of authority from a delegator to a delegate.

    Example:
        Portfolio Manager (50M max)
            delegates to
        Deputy (20M max, today 9:00-18:00)

    The Deputy CANNOT approve 30M even though the PM can approve 50M.
    The delegation limit (20M) caps what the delegate can do.
    """

    delegation_id: str
    delegator: str          # Original authority holder
    delegate: str           # Person receiving the delegation

    # Derived from which grant
    parent_grant_id: str = ""

    # Scope and limits (must be subset of parent)
    scope: Optional[DelegationScope] = None
    limit: Optional[DelegationLimit] = None

    # Validity window
    valid_from: float = 0.0
    valid_to: float = float("inf")

    # Status
    status: DelegationStatus = DelegationStatus.DRAFT

    # Sub-delegation
    allow_subdelegation: bool = False
    delegation_depth: int = 0

    # Reason / justification
    reason: str = ""

    # Meta
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    activated_at: Optional[float] = None
    revoked_at: Optional[float] = None

    @classmethod
    def create(
        cls,
        delegator: str,
        delegate: str,
        parent_grant: AuthorityGrant,
        scope: Optional[DelegationScope] = None,
        limit: Optional[DelegationLimit] = None,
        reason: str = "",
        valid_from: float = 0.0,
        valid_to: float = float("inf"),
        allow_subdelegation: bool = False,
    ) -> "Delegation":
        """Factory to create a delegation."""
        delegation_id = f"DEL-{int(time.time() * 1_000_000)}-{uuid.uuid4().hex[:6]}"
        now = time.time()
        if valid_from <= 0:
            valid_from = now

        return cls(
            delegation_id=delegation_id,
            delegator=delegator,
            delegate=delegate,
            parent_grant_id=parent_grant.grant_id,
            scope=scope,
            limit=limit,
            valid_from=valid_from,
            valid_to=valid_to,
            reason=reason,
            allow_subdelegation=allow_subdelegation,
            delegation_depth=0,
            created_at=now,
            updated_at=now,
        )

    def is_active(self, current_time: Optional[float] = None) -> bool:
        """Check if the delegation is currently active."""
        if self.status != DelegationStatus.ACTIVE:
            return False
        now = current_time or time.time()
        return self.valid_from <= now <= self.valid_to

    def activate(self) -> None:
        """Activate the delegation."""
        from .delegation_status import can_activate
        if not can_activate(self.status):
            raise ValueError(f"Cannot activate delegation from {self.status.name}")
        self.status = DelegationStatus.ACTIVE
        self.activated_at = time.time()
        self.updated_at = time.time()

    def revoke(self, actor: str = "SYSTEM", reason: str = "") -> None:
        """Revoke the delegation."""
        self.status = DelegationStatus.REVOKED
        self.revoked_at = time.time()
        self.updated_at = time.time()

    def expire(self) -> None:
        """Mark as expired."""
        self.status = DelegationStatus.EXPIRED
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delegation_id": self.delegation_id,
            "delegator": self.delegator,
            "delegate": self.delegate,
            "parent_grant_id": self.parent_grant_id,
            "scope": self.scope.to_dict() if self.scope else None,
            "limit": self.limit.to_dict() if self.limit else None,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "status": self.status.name,
            "allow_subdelegation": self.allow_subdelegation,
            "delegation_depth": self.delegation_depth,
            "reason": self.reason,
            "created_at": self.created_at,
            "activated_at": self.activated_at,
            "revoked_at": self.revoked_at,
        }


# ----------------------------------------------------------------------
# Commit 28 Part 1.4 — Approval Delegation & Authority Boundary
#
# The classes above (Delegation / DelegationValidator) are the Commit 20
# legacy delegation model.  Part 1.4 introduces a *scoped, time-bound*
# delegation model that answers "有资格批准 != 现在有权批准":
#
#   AuthorityDelegation          — who delegates what, for how long
#   ScopedDelegationValidator    — runtime validity (enabled / principal /
#                                  resource / action / time window)
#   DelegationAuthorityValidator — authority boundary: delegated authority
#                                  must be a SUBSET of the delegator's
#                                  effective authority (no escalation)
#   can_delegate()               — chain prevention: delegated authority
#                                  cannot delegate again (A->B ok, A->B->C no)
#   EmergencyDelegation          — short, fixed-scope, auto-expiring
#                                  emergency delegation (never permanent)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class AuthorityDelegation:
    """A scoped, time-bound transfer of approval authority.

    Delegation is NOT a role transfer: it grants the delegate a *limited*
    slice of the delegator's authority for one resource and a fixed set of
    actions, inside a hard validity window.
    """

    delegation_id: str
    delegator_id: str
    delegate_id: str
    resource: str
    actions: tuple[str, ...]
    valid_from: datetime
    valid_until: datetime
    enabled: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "actions", tuple(self.actions))


class ScopedDelegationValidator:
    """Runtime validity check for an :class:`AuthorityDelegation`.

    A delegation is valid only when ALL of the following hold:
      - the delegation is enabled;
      - the acting principal is the delegate;
      - the resource matches exactly;
      - the action is inside the delegated action set;
      - ``now`` is inside [valid_from, valid_until).
    """

    def is_valid(
        self,
        delegation: AuthorityDelegation,
        principal_id: str,
        resource: str,
        action: str,
        now: datetime,
    ) -> bool:
        if not delegation.enabled:
            return False
        if delegation.delegate_id != principal_id:
            return False
        if delegation.resource != resource:
            return False
        if action not in delegation.actions:
            return False
        if now < delegation.valid_from:
            return False
        if now >= delegation.valid_until:
            return False
        return True


class DelegationAuthorityValidator:
    """No privilege escalation: delegated authority must fit inside the
    delegator's effective authority.

        Delegated Authority ⊆ Delegator Authority

    A principal holding only ``trading: pause, resume`` may delegate
    ``pause`` but never ``kill``.
    """

    def validate(
        self,
        delegator_authority,
        delegation: AuthorityDelegation,
    ) -> bool:
        if delegation.resource != delegator_authority.resource:
            return False
        allowed = set(delegator_authority.actions)
        requested = set(delegation.actions)
        return requested.issubset(allowed)


def can_delegate(authority) -> bool:
    """Chain prevention: delegated authority cannot delegate again.

    ``A -> B`` is allowed; ``A -> B -> C`` is forbidden, because B's
    authority has source DELEGATION.
    """
    return getattr(authority, "source", "ROLE") != "DELEGATION"


@dataclass(frozen=True)
class EmergencyDelegation:
    """A short-lived, fixed-scope emergency delegation.

    Emergency delegation must be:
      - time-bound (valid_from / valid_until);
      - scope-bound (exactly one resource and one action);
      - auto-expiring (never a permanent grant);
      - capped in duration (max_duration_seconds).
    """

    delegation_id: str
    delegator_id: str
    delegate_id: str
    resource: str
    action: str
    valid_from: datetime
    valid_until: datetime
    max_duration_seconds: int = 1800
    enabled: bool = True

    @property
    def duration_seconds(self) -> float:
        return (self.valid_until - self.valid_from).total_seconds()

    def is_expired(self, now: datetime) -> bool:
        return now >= self.valid_until

    def is_valid(self, now: datetime) -> bool:
        if not self.enabled:
            return False
        if now < self.valid_from or now >= self.valid_until:
            return False
        if self.duration_seconds > self.max_duration_seconds:
            return False
        return True
