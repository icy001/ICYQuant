"""
Authority Grant — records an explicit grant of authority to an actor.

Grants are explicit, revocable, time-bound permissions. No implicit authority
exists — every actor's permissions derive from explicit grants.

Key security principle:
  Permission must be explicitly granted. Absence of a deny is not a grant.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .authority_scope import AuthorityScope, AuthorityScopeLevel
from .authority_limit import AuthorityLimit
from .authority_policy import AuthorityLevel


@dataclass
class AuthorityGrant:
    """
    An explicit authority grant for an actor.

    Example:
        GRANT-001:
            actor: RISK_MANAGER
            scope: PORTFOLIO
            actions: [APPROVE_ALLOCATION]
            limit: 20M
            valid: 2026-08-01 to 2026-12-31
    """

    grant_id: str
    actor: str
    actor_name: str = ""

    # What authority level
    authority_level: AuthorityLevel = AuthorityLevel.RECOMMENDATION

    # Scope — what domain
    scope: Optional[AuthorityScope] = None

    # Limits — what quantities
    limit: Optional[AuthorityLimit] = None

    # Validity
    valid_from: float = 0.0
    valid_to: float = float("inf")

    # Status
    active: bool = True

    # Who granted this
    granted_by: str = "SYSTEM"
    reason: str = ""

    # Meta
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    revoked_at: Optional[float] = None

    @classmethod
    def create(
        cls,
        actor: str,
        authority_level: AuthorityLevel,
        scope: Optional[AuthorityScope] = None,
        limit: Optional[AuthorityLimit] = None,
        granted_by: str = "SYSTEM",
        reason: str = "",
        valid_from: float = 0.0,
        valid_to: float = float("inf"),
    ) -> "AuthorityGrant":
        """Factory method to create a new grant with auto-generated ID."""
        grant_id = f"GRANT-{int(time.time() * 1_000_000)}-{uuid.uuid4().hex[:6]}"
        now = time.time()
        if valid_from <= 0:
            valid_from = now
        return cls(
            grant_id=grant_id,
            actor=actor,
            authority_level=authority_level,
            scope=scope,
            limit=limit,
            valid_from=valid_from,
            valid_to=valid_to,
            granted_by=granted_by,
            reason=reason,
            created_at=now,
            updated_at=now,
        )

    def is_valid(self, current_time: Optional[float] = None) -> bool:
        """Check if the grant is currently active and valid."""
        if not self.active:
            return False
        now = current_time or time.time()
        return self.valid_from <= now <= self.valid_to

    def revoke(self, actor: str = "SYSTEM", reason: str = "") -> None:
        """Revoke this grant."""
        self.active = False
        self.revoked_at = time.time()
        self.updated_at = time.time()

    def can_approve_amount(self, amount: float) -> bool:
        """Check if this grant allows approving the given amount."""
        if self.limit is None:
            return True
        return self.limit.allows_amount(amount)

    def can_approve_risk(self, risk: float) -> bool:
        """Check if this grant allows approving the given risk level."""
        if self.limit is None:
            return True
        return self.limit.allows_risk(risk)

    def can_approve_action(self, action: str) -> bool:
        """Check if this grant allows the given action."""
        if self.limit is None:
            return True
        return self.limit.allows_action(action)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "grant_id": self.grant_id,
            "actor": self.actor,
            "actor_name": self.actor_name,
            "authority_level": self.authority_level.name,
            "scope": self.scope.to_dict() if self.scope else None,
            "limit": self.limit.to_dict() if self.limit else None,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "active": self.active,
            "granted_by": self.granted_by,
            "reason": self.reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "revoked_at": self.revoked_at,
        }
