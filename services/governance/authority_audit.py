"""
Authority Audit — tracks all authority changes (grants, modifications, revocations).

Every authority change is recorded with:
  - Who performed the change
  - What was changed
  - When it happened
  - Why it happened

This provides full traceability for the authority lifecycle.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class AuthorityAuditAction(Enum):
    """Types of authority changes that are audited."""
    GRANT = auto()
    MODIFY = auto()
    REVOKE = auto()
    DELEGATE = auto()
    EXPIRE = auto()
    ACTIVATE = auto()
    DEACTIVATE = auto()
    SUSPEND = auto()
    RESTORE = auto()


@dataclass
class AuthorityAuditRecord:
    """
    A single authority change audit record.

    Example:
        AUTH-001
            Risk Manager
            Granted: 20M
            By: Governance Administrator
            Effective: 2026-08-01
    """

    audit_id: str
    action: AuthorityAuditAction

    # Who
    actor: str = ""
    actor_name: str = ""
    performed_by: str = ""

    # What
    grant_id: str = ""
    authority_level: str = ""
    scope: str = ""
    max_amount: float = 0.0

    # Changes (for MODIFY actions)
    previous_values: Dict[str, Any] = field(default_factory=dict)
    new_values: Dict[str, Any] = field(default_factory=dict)

    # Delegation context
    delegation_id: str = ""
    delegator: str = ""
    delegate: str = ""

    # Reason
    reason: str = ""

    # Timing
    effective_from: float = 0.0
    effective_to: float = 0.0
    timestamp: float = field(default_factory=time.time)

    @classmethod
    def create_grant_record(
        cls,
        actor: str,
        grant_id: str,
        authority_level: str,
        max_amount: float,
        scope: str = "",
        performed_by: str = "SYSTEM",
        reason: str = "",
    ) -> "AuthorityAuditRecord":
        """Create an audit record for a grant."""
        return cls(
            audit_id=f"AUTH-AUDIT-{int(time.time() * 1_000_000)}-{uuid.uuid4().hex[:6]}",
            action=AuthorityAuditAction.GRANT,
            actor=actor,
            grant_id=grant_id,
            authority_level=authority_level,
            scope=scope,
            max_amount=max_amount,
            performed_by=performed_by,
            reason=reason,
        )

    @classmethod
    def create_revoke_record(
        cls,
        actor: str,
        grant_id: str,
        authority_level: str,
        max_amount: float,
        performed_by: str = "SYSTEM",
        reason: str = "",
    ) -> "AuthorityAuditRecord":
        """Create an audit record for a revocation."""
        return cls(
            audit_id=f"AUTH-AUDIT-{int(time.time() * 1_000_000)}-{uuid.uuid4().hex[:6]}",
            action=AuthorityAuditAction.REVOKE,
            actor=actor,
            grant_id=grant_id,
            authority_level=authority_level,
            max_amount=max_amount,
            performed_by=performed_by,
            reason=reason,
        )

    @classmethod
    def create_delegation_record(
        cls,
        delegator: str,
        delegate: str,
        delegation_id: str,
        max_amount: float,
        performed_by: str = "SYSTEM",
        reason: str = "",
    ) -> "AuthorityAuditRecord":
        """Create an audit record for a delegation."""
        return cls(
            audit_id=f"AUTH-AUDIT-{int(time.time() * 1_000_000)}-{uuid.uuid4().hex[:6]}",
            action=AuthorityAuditAction.DELEGATE,
            actor=delegator,
            delegation_id=delegation_id,
            delegator=delegator,
            delegate=delegate,
            max_amount=max_amount,
            performed_by=performed_by,
            reason=reason,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "action": self.action.name,
            "actor": self.actor,
            "actor_name": self.actor_name,
            "performed_by": self.performed_by,
            "grant_id": self.grant_id,
            "authority_level": self.authority_level,
            "scope": self.scope,
            "max_amount": self.max_amount,
            "previous_values": self.previous_values,
            "new_values": self.new_values,
            "delegation_id": self.delegation_id,
            "delegator": self.delegator,
            "delegate": self.delegate,
            "reason": self.reason,
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
            "timestamp": self.timestamp,
        }


class AuthorityAuditStore:
    """
    Persistent store for authority audit records.

    Provides query capabilities:
      - By actor
      - By time range
      - By action type
      - By grant
    """

    def __init__(self):
        self._records: List[AuthorityAuditRecord] = []

    def record(self, audit: AuthorityAuditRecord) -> None:
        """Store an audit record."""
        self._records.append(audit)

    def get_by_actor(self, actor: str) -> List[AuthorityAuditRecord]:
        """Get all records for an actor."""
        return [r for r in self._records if r.actor == actor]

    def get_by_grant(self, grant_id: str) -> List[AuthorityAuditRecord]:
        """Get all records for a grant."""
        return [r for r in self._records if r.grant_id == grant_id]

    def get_by_action(self, action: AuthorityAuditAction) -> List[AuthorityAuditRecord]:
        """Get all records of a specific action type."""
        return [r for r in self._records if r.action == action]

    def get_by_time_range(self, start: float, end: float) -> List[AuthorityAuditRecord]:
        """Get records within a time range."""
        return [r for r in self._records if start <= r.timestamp <= end]

    def get_all(self) -> List[AuthorityAuditRecord]:
        """Get all records."""
        return list(self._records)

    def count(self) -> int:
        """Total records."""
        return len(self._records)
