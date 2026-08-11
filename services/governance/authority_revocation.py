"""
Authority Revocation — records the revocation of an authority grant.

Revocations are explicit, auditable events. Once revoked:
  - The grant is marked inactive
  - In-flight approvals using that grant are invalidated
  - New requests cannot use the revoked grant

Revocation ≠ Deletion: the grant history is preserved for audit.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .authority_grant import AuthorityGrant


# ---------------------------------------------------------------------------
# Revocation record
# ---------------------------------------------------------------------------

@dataclass
class AuthorityRevocation:
    """
    Record of an authority grant revocation.

    Example:
        Auth-001
          Risk Manager, 20M
          Revoked 2026-08-11 by Governance Administrator
          Reason: Position transfer
    """

    revocation_id: str
    grant_id: str
    actor: str  # The actor whose authority was revoked
    revoked_by: str  # Who performed the revocation
    reason: str = ""

    # What was revoked
    original_scope: str = ""
    original_max_amount: float = 0.0
    original_authority_level: str = ""

    # In-flight approval impact
    invalidated_approval_ids: List[str] = field(default_factory=list)

    # Timing
    revoked_at: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)

    @classmethod
    def from_grant(
        cls,
        grant: AuthorityGrant,
        revoked_by: str,
        reason: str = "",
        invalidated_approval_ids: Optional[List[str]] = None,
    ) -> "AuthorityRevocation":
        """Create a revocation record from a grant."""
        revocation_id = f"REV-{int(time.time() * 1_000_000)}-{uuid.uuid4().hex[:6]}"
        return cls(
            revocation_id=revocation_id,
            grant_id=grant.grant_id,
            actor=grant.actor,
            revoked_by=revoked_by,
            reason=reason,
            original_scope=grant.scope.level.name if grant.scope else "",
            original_max_amount=grant.limit.max_amount if grant.limit else 0.0,
            original_authority_level=grant.authority_level.name,
            invalidated_approval_ids=invalidated_approval_ids or [],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "revocation_id": self.revocation_id,
            "grant_id": self.grant_id,
            "actor": self.actor,
            "revoked_by": self.revoked_by,
            "reason": self.reason,
            "original_scope": self.original_scope,
            "original_max_amount": self.original_max_amount,
            "original_authority_level": self.original_authority_level,
            "invalidated_approval_ids": self.invalidated_approval_ids,
            "revoked_at": self.revoked_at,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Revocation Registry
# ---------------------------------------------------------------------------

class AuthorityRevocationRegistry:
    """
    Tracks and manages authority revocations.

    Ensures:
      - Revocations are recorded and auditable
      - In-flight approvals can be invalidated on revocation
      - Revoked actors cannot be re-granted without explicit new grant
    """

    def __init__(self):
        self._revocations: Dict[str, AuthorityRevocation] = {}
        self._revoked_grant_ids: set = set()

    def record(self, revocation: AuthorityRevocation) -> None:
        """Record a revocation."""
        self._revocations[revocation.revocation_id] = revocation
        self._revoked_grant_ids.add(revocation.grant_id)

    def is_revoked(self, grant_id: str) -> bool:
        """Check if a grant has been revoked."""
        return grant_id in self._revoked_grant_ids

    def get_revocation(self, revocation_id: str) -> Optional[AuthorityRevocation]:
        """Get a revocation by ID."""
        return self._revocations.get(revocation_id)

    def get_revocations_for_actor(self, actor: str) -> List[AuthorityRevocation]:
        """Get all revocations for an actor."""
        return [r for r in self._revocations.values() if r.actor == actor]

    def list_revocations(self) -> List[AuthorityRevocation]:
        """List all revocations."""
        return list(self._revocations.values())

    def revoke_grant(
        self,
        grant: AuthorityGrant,
        revoked_by: str,
        reason: str = "",
        invalidated_approval_ids: Optional[List[str]] = None,
    ) -> AuthorityRevocation:
        """Revoke a grant and record it."""
        revocation = AuthorityRevocation.from_grant(
            grant, revoked_by, reason, invalidated_approval_ids
        )
        grant.revoke(revoked_by, reason)
        self.record(revocation)
        return revocation
