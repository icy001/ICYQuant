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
