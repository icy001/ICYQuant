"""
Rotation audit logging.

Records detailed audit entries for
all rotation operations, providing
complete traceability for compliance
and forensic analysis.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class RotationAuditAction(str, Enum):
    """Rotation audit action types."""

    ROTATION_STARTED = "rotation_started"
    ROTATION_COMPLETED = "rotation_completed"
    ROTATION_FAILED = "rotation_failed"
    ROTATION_ROLLED_BACK = "rotation_rolled_back"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_APPROVED = "approval_approved"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_EXPIRED = "approval_expired"
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"
    TRANSITION_BEGUN = "transition_begun"
    TRANSITION_VERIFIED = "transition_verified"
    TRANSITION_COMPLETED = "transition_completed"
    TRANSITION_ROLLED_BACK = "transition_rolled_back"
    SCHEDULE_CREATED = "schedule_created"
    SCHEDULE_EXECUTED = "schedule_executed"
    SCHEDULE_FAILED = "schedule_failed"
    NOTIFICATION_SENT = "notification_sent"


@dataclass
class RotationAuditEntry:
    """
    A single rotation audit entry.

    Records all relevant context for
    a rotation operation for compliance
    and forensic review.

    Attributes:
        entry_id: Unique entry identifier.
        action: Audit action performed.
        secret_key: Target secret key.
        operator: Who performed the action.
        old_version: Previous version.
        new_version: New version.
        reason: Reason for the action.
        trace_id: Correlation trace ID.
        metadata: Additional context.
        timestamp: When the action occurred.
    """

    entry_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    action: RotationAuditAction = RotationAuditAction.ROTATION_STARTED
    secret_key: str = ""
    operator: str = "system"
    old_version: Optional[int] = None
    new_version: Optional[int] = None
    reason: str = ""
    trace_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "action": self.action.value,
            "secret_key": self.secret_key,
            "operator": self.operator,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "reason": self.reason,
            "trace_id": self.trace_id,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat() + "Z",
        }


class RotationAudit:
    """
    Rotation audit logger.

    Records and stores rotation audit
    entries with filtering and querying
    capabilities for compliance reporting.

    Usage:
        audit = RotationAudit()
        audit.log(
            action=RotationAuditAction.ROTATION_STARTED,
            secret_key="database/password",
            operator="admin",
        )
        entries = audit.query(secret_key="database/password")
    """

    MAX_ENTRIES = 10000

    def __init__(
        self,
        on_log: Optional[Callable[[RotationAuditEntry], None]] = None,
    ) -> None:
        """
        Initialize audit logger.

        Args:
            on_log: Callback for new audit entries
                   (e.g., for external shipping).
        """
        self._entries: List[RotationAuditEntry] = []
        self._on_log = on_log
        self._action_counts: Dict[str, int] = {}

    def log(
        self,
        action: RotationAuditAction,
        secret_key: str = "",
        operator: str = "system",
        old_version: Optional[int] = None,
        new_version: Optional[int] = None,
        reason: str = "",
        trace_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RotationAuditEntry:
        """
        Create and store an audit entry.

        Args:
            action: Action performed.
            secret_key: Target secret key.
            operator: Who performed the action.
            old_version: Previous version.
            new_version: New version.
            reason: Action reason.
            trace_id: Correlation ID.
            metadata: Additional context.

        Returns:
            Created RotationAuditEntry.
        """
        entry = RotationAuditEntry(
            action=action,
            secret_key=secret_key,
            operator=operator,
            old_version=old_version,
            new_version=new_version,
            reason=reason,
            trace_id=trace_id or uuid.uuid4().hex[:8],
            metadata=metadata or {},
        )

        self._entries.append(entry)
        self._action_counts[action.value] = (
            self._action_counts.get(action.value, 0) + 1
        )

        # Trim if over limit
        if len(self._entries) > self.MAX_ENTRIES:
            self._entries = self._entries[-self.MAX_ENTRIES:]

        # External shipping
        if self._on_log:
            try:
                self._on_log(entry)
            except Exception as e:
                logger.error("Audit callback error: %s", e)

        return entry

    def query(
        self,
        secret_key: Optional[str] = None,
        action: Optional[RotationAuditAction] = None,
        operator: Optional[str] = None,
        limit: int = 50,
    ) -> List[RotationAuditEntry]:
        """
        Query audit entries with filters.

        Args:
            secret_key: Filter by secret key.
            action: Filter by action type.
            operator: Filter by operator.
            limit: Maximum entries to return.

        Returns:
            List of matching audit entries.
        """
        entries = list(reversed(self._entries))

        if secret_key:
            entries = [e for e in entries if e.secret_key == secret_key]
        if action:
            entries = [e for e in entries if e.action == action]
        if operator:
            entries = [e for e in entries if e.operator == operator]

        return entries[:limit]

    def get_by_trace(
        self,
        trace_id: str,
    ) -> List[RotationAuditEntry]:
        """
        Get all entries for a trace ID.

        Args:
            trace_id: Trace ID to look up.

        Returns:
            List of entries with matching trace ID.
        """
        return [e for e in self._entries if e.trace_id == trace_id]

    def get_entry(
        self,
        entry_id: str,
    ) -> Optional[RotationAuditEntry]:
        """Get a specific audit entry by ID."""
        for entry in self._entries:
            if entry.entry_id == entry_id:
                return entry
        return None

    def export(
        self,
        secret_key: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Export audit entries as dictionaries.

        Args:
            secret_key: Filter by secret key.
            limit: Max entries to export.

        Returns:
            List of entry dictionaries.
        """
        entries = self.query(secret_key=secret_key, limit=limit)
        return [e.to_dict() for e in entries]

    def clear(self) -> None:
        """Clear all audit entries."""
        self._entries.clear()
        self._action_counts.clear()

    def count(self) -> int:
        """Get total entry count."""
        return len(self._entries)

    def get_stats(self) -> Dict[str, Any]:
        """Get audit statistics."""
        return {
            "total_entries": len(self._entries),
            "action_counts": dict(self._action_counts),
            "storage_limit": self.MAX_ENTRIES,
            "utilization_pct": round(
                len(self._entries) / self.MAX_ENTRIES * 100, 1
            ),
        }
