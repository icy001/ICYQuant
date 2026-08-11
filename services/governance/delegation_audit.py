"""
Delegation Audit — tracks all delegation lifecycle changes.

Every delegation change is recorded:
  - CREATED: who delegated, to whom, what limits
  - ACTIVATED: when delegation became active
  - REVOKED: who revoked, why
  - EXPIRED: natural expiration
  - SUPERSEDED: replaced by a newer delegation

This provides full traceability for the delegation lifecycle.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class DelegationAuditAction(Enum):
    """Types of delegation changes audited."""
    CREATED = auto()
    ACTIVATED = auto()
    REVOKED = auto()
    EXPIRED = auto()
    SUPERSEDED = auto()
    MODIFIED = auto()


@dataclass
class DelegationAuditRecord:
    """
    A single delegation audit record.

    Example:
        DEL-001
            From: Portfolio Manager
            To: Deputy
            Scope: Portfolio A
            Limit: 10M
            Valid: 09:00 - 18:00
            Reason: Temporary coverage
    """

    audit_id: str
    action: DelegationAuditAction

    # Parties
    delegation_id: str = ""
    delegator: str = ""
    delegate: str = ""

    # What was delegated
    scope: str = ""
    max_amount: float = 0.0
    allowed_actions: List[str] = field(default_factory=list)

    # Timing
    valid_from: float = 0.0
    valid_to: float = 0.0

    # Execution context
    performed_by: str = "SYSTEM"
    reason: str = ""

    # Meta
    timestamp: float = field(default_factory=time.time)

    @classmethod
    def create_record(
        cls,
        action: DelegationAuditAction,
        delegation_id: str,
        delegator: str,
        delegate: str,
        max_amount: float = 0.0,
        scope: str = "",
        reason: str = "",
        valid_from: float = 0.0,
        valid_to: float = 0.0,
        performed_by: str = "SYSTEM",
    ) -> "DelegationAuditRecord":
        """Create a delegation audit record."""
        return cls(
            audit_id=f"DEL-AUDIT-{int(time.time() * 1_000_000)}-{uuid.uuid4().hex[:6]}",
            action=action,
            delegation_id=delegation_id,
            delegator=delegator,
            delegate=delegate,
            scope=scope,
            max_amount=max_amount,
            valid_from=valid_from,
            valid_to=valid_to,
            performed_by=performed_by,
            reason=reason,
        )

    @classmethod
    def created(
        cls,
        delegation_id: str,
        delegator: str,
        delegate: str,
        max_amount: float = 0.0,
        scope: str = "",
        reason: str = "",
        valid_from: float = 0.0,
        valid_to: float = 0.0,
    ) -> "DelegationAuditRecord":
        """Record delegation creation."""
        return cls.create_record(
            action=DelegationAuditAction.CREATED,
            delegation_id=delegation_id,
            delegator=delegator,
            delegate=delegate,
            max_amount=max_amount,
            scope=scope,
            reason=reason,
            valid_from=valid_from,
            valid_to=valid_to,
        )

    @classmethod
    def revoked(
        cls,
        delegation_id: str,
        delegator: str,
        delegate: str,
        reason: str = "",
        performed_by: str = "SYSTEM",
    ) -> "DelegationAuditRecord":
        """Record delegation revocation."""
        return cls.create_record(
            action=DelegationAuditAction.REVOKED,
            delegation_id=delegation_id,
            delegator=delegator,
            delegate=delegate,
            reason=reason,
            performed_by=performed_by,
        )

    @classmethod
    def expired(
        cls,
        delegation_id: str,
        delegator: str,
        delegate: str,
    ) -> "DelegationAuditRecord":
        """Record natural expiration."""
        return cls.create_record(
            action=DelegationAuditAction.EXPIRED,
            delegation_id=delegation_id,
            delegator=delegator,
            delegate=delegate,
            reason="Natural expiration",
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "action": self.action.name,
            "delegation_id": self.delegation_id,
            "delegator": self.delegator,
            "delegate": self.delegate,
            "scope": self.scope,
            "max_amount": self.max_amount,
            "allowed_actions": self.allowed_actions,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "performed_by": self.performed_by,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


class DelegationAuditStore:
    """
    Persistent store for delegation audit records.

    Query by delegator, delegate, action, or time range.
    """

    def __init__(self):
        self._records: List[DelegationAuditRecord] = []

    def record(self, audit: DelegationAuditRecord) -> None:
        """Store an audit record."""
        self._records.append(audit)

    def get_by_delegator(self, delegator: str) -> List[DelegationAuditRecord]:
        """Get all records for a delegator."""
        return [r for r in self._records if r.delegator == delegator]

    def get_by_delegate(self, delegate: str) -> List[DelegationAuditRecord]:
        """Get all records for a delegate."""
        return [r for r in self._records if r.delegate == delegate]

    def get_by_delegation(self, delegation_id: str) -> List[DelegationAuditRecord]:
        """Get all records for a specific delegation."""
        return [r for r in self._records if r.delegation_id == delegation_id]

    def get_by_action(self, action: DelegationAuditAction) -> List[DelegationAuditRecord]:
        """Get records by action type."""
        return [r for r in self._records if r.action == action]

    def get_by_time_range(self, start: float, end: float) -> List[DelegationAuditRecord]:
        """Get records within a time range."""
        return [r for r in self._records if start <= r.timestamp <= end]

    def get_all(self) -> List[DelegationAuditRecord]:
        """Get all records."""
        return list(self._records)

    def count(self) -> int:
        """Total records."""
        return len(self._records)
