"""
ICYQuant Audit Service — comprehensive audit logging for data platform operations.

Tracks all data access, modifications, governance actions, and API calls
with structured audit events for compliance and security monitoring.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    # Data access
    DATA_QUERY = "data:query"
    DATA_SUBSCRIBE = "data:subscribe"
    DATA_REPLAY = "data:replay"
    DATA_PUBLISH = "data:publish"
    DATA_INGEST = "data:ingest"
    DATA_DELETE = "data:delete"

    # Governance
    GOVERNANCE_CHECK = "governance:check"
    GOVERNANCE_UPDATE = "governance:update"
    LINEAGE_TRACK = "lineage:track"
    QUALITY_CHECK = "quality:check"
    RETENTION_APPLY = "retention:apply"

    # Access control
    ACCESS_GRANT = "access:grant"
    ACCESS_REVOKE = "access:revoke"
    ACCESS_DENY = "access:deny"
    ROLE_ASSIGN = "role:assign"
    ROLE_REVOKE = "role:revoke"

    # API
    API_REQUEST = "api:request"
    API_ERROR = "api:error"

    # Admin
    CONFIG_CHANGE = "config:change"
    SYSTEM_START = "system:start"
    SYSTEM_STOP = "system:stop"


class AuditSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """A single audit event."""
    event_id: str
    action: AuditAction
    principal_id: str
    severity: AuditSeverity = AuditSeverity.INFO
    resource_type: str = ""
    resource_id: str = ""
    detail: str = ""
    result: str = "success"
    source_ip: str = ""
    user_agent: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class AuditService:
    """Comprehensive audit logging service.

    Tracks:
        - Data access events (query, subscribe, replay, publish)
        - Governance actions (checks, updates)
        - Access control changes (grants, revokes, role assignments)
        - API requests and errors
        - System configuration changes

    Provides querying, filtering, and export for compliance.
    """

    def __init__(self, max_events: int = 100_000) -> None:
        self._max_events = max_events
        self._events: OrderedDict[str, AuditEvent] = OrderedDict()
        self._total_logged = 0
        self._enabled = True

    def log(
        self,
        action: AuditAction,
        principal_id: str,
        severity: AuditSeverity = AuditSeverity.INFO,
        resource_type: str = "",
        resource_id: str = "",
        detail: str = "",
        result: str = "success",
        source_ip: str = "",
        user_agent: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> AuditEvent:
        """Log an audit event."""
        if not self._enabled:
            return None

        import uuid

        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            action=action,
            principal_id=principal_id,
            severity=severity,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail,
            result=result,
            source_ip=source_ip,
            user_agent=user_agent,
            metadata=metadata or {},
        )

        # Enforce capacity
        if len(self._events) >= self._max_events:
            self._events.popitem(last=False)

        self._events[event.event_id] = event
        self._total_logged += 1

        log_level = {
            AuditSeverity.INFO: logging.INFO,
            AuditSeverity.WARNING: logging.WARNING,
            AuditSeverity.ERROR: logging.ERROR,
            AuditSeverity.CRITICAL: logging.CRITICAL,
        }.get(severity, logging.INFO)

        logger.log(log_level, "AUDIT | %s | %s | %s | %s",
                   action.value, principal_id, resource_id, result)

        return event

    def query(
        self,
        principal_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        resource_id: Optional[str] = None,
        severity: Optional[AuditSeverity] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Query audit events with filters."""
        results: list[AuditEvent] = []

        for event in reversed(self._events.values()):
            if principal_id and event.principal_id != principal_id:
                continue
            if action and event.action != action:
                continue
            if resource_id and event.resource_id != resource_id:
                continue
            if severity and event.severity != severity:
                continue
            if start_time and event.timestamp < start_time:
                continue
            if end_time and event.timestamp > end_time:
                continue

            results.append(event)
            if len(results) >= limit:
                break

        return results

    def get_event(self, event_id: str) -> Optional[AuditEvent]:
        return self._events.get(event_id)

    def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent audit events as dictionaries."""
        events = list(self._events.values())[-limit:]
        return [
            {
                "event_id": e.event_id,
                "action": e.action.value,
                "principal_id": e.principal_id,
                "severity": e.severity.value,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "detail": e.detail,
                "result": e.result,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in reversed(events)
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get audit statistics."""
        action_counts: dict[str, int] = {}
        severity_counts: dict[str, int] = {}
        error_count = 0

        for event in self._events.values():
            a = event.action.value
            action_counts[a] = action_counts.get(a, 0) + 1
            s = event.severity.value
            severity_counts[s] = severity_counts.get(s, 0) + 1
            if event.result != "success":
                error_count += 1

        return {
            "total_events": len(self._events),
            "total_logged": self._total_logged,
            "error_count": error_count,
            "by_action": action_counts,
            "by_severity": severity_counts,
        }

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def clear(self) -> int:
        """Clear all audit events. Returns count cleared."""
        count = len(self._events)
        self._events.clear()
        return count

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def total_logged(self) -> int:
        return self._total_logged
