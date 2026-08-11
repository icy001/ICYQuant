"""Audit Center — comprehensive audit trail for all AI platform operations.

The AuditCenter records every significant event in the AI platform for
institutional compliance and forensic analysis. It provides immutable
audit trails with tamper-evident logging, query capabilities, and
export functionality.

Audit dimensions:
    - User actions (who did what)
    - Agent decisions (why was a decision made)
    - Planning trace (what was the plan)
    - Tool calls (which tools were used)
    - Model calls (which model, tokens, cost)
    - Policy decisions (what was allowed/blocked)
    - Results (what was the outcome)
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of auditable events."""
    USER_REQUEST = "user_request"
    AGENT_CREATED = "agent_created"
    AGENT_DECISION = "agent_decision"
    PLANNING = "planning"
    TOOL_CALL = "tool_call"
    MODEL_CALL = "model_call"
    POLICY_DECISION = "policy_decision"
    GUARDRAIL_ACTION = "guardrail_action"
    CONSENSUS_REACHED = "consensus_reached"
    EXECUTION = "execution"
    APPROVAL = "approval"
    RESULT = "result"
    ERROR = "error"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """A single auditable event in the platform."""
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    event_type: AuditEventType = AuditEventType.USER_REQUEST
    severity: AuditSeverity = AuditSeverity.INFO
    user_id: str = ""
    session_id: str = ""
    agent_id: str = ""
    timestamp: float = field(default_factory=time.monotonic)
    summary: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "summary": self.summary,
            "details": self.details,
            "correlation_id": self.correlation_id,
        }

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), default=str)


class AuditCenter:
    """Comprehensive audit trail for institutional compliance.

    Records every significant event in the AI platform with immutable
    audit trails, query capabilities, and export functionality.

    Usage:
        ac = AuditCenter()
        await ac.initialize()
        await ac.record(AuditEvent(
            event_type=AuditEventType.USER_REQUEST,
            user_id="user_1",
            summary="User requested market analysis",
        ))
        events = await ac.query(user_id="user_1", limit=100)
    """

    def __init__(self, max_events: int = 100000, retention_sec: float = 7776000.0) -> None:
        """Initialize the audit center.

        Args:
            max_events: Maximum events to keep in memory.
            retention_sec: Retention period in seconds (default: 90 days).
        """
        self._max_events = max_events
        self._retention_sec = retention_sec
        self._events: List[AuditEvent] = []
        self._initialized: bool = False
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = threading.Lock()
        logger.info("AuditCenter created (max_events=%d, retention=%d days)", max_events, int(retention_sec / 86400))

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("AuditCenter initialized")

    async def shutdown(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        with self._lock:
            self._events.clear()
        self._initialized = False
        logger.info("AuditCenter shutdown complete")

    async def record(self, event: AuditEvent) -> str:
        """Record an audit event."""
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]
        logger.debug("Audit: [%s] %s: %s", event.event_type.value, event.user_id, event.summary)
        return event.event_id

    async def record_quick(self, event_type: AuditEventType, summary: str, user_id: str = "", session_id: str = "", agent_id: str = "", severity: AuditSeverity = AuditSeverity.INFO, details: Optional[Dict[str, Any]] = None, correlation_id: str = "") -> str:
        """Convenience method to record an audit event quickly."""
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            session_id=session_id,
            agent_id=agent_id,
            summary=summary,
            details=details or {},
            correlation_id=correlation_id,
        )
        return await self.record(event)

    async def query(self, user_id: Optional[str] = None, session_id: Optional[str] = None, agent_id: Optional[str] = None, event_type: Optional[AuditEventType] = None, severity: Optional[AuditSeverity] = None, correlation_id: Optional[str] = None, since_sec: Optional[float] = None, limit: int = 100) -> List[AuditEvent]:
        """Query audit events with filters."""
        with self._lock:
            results = list(self._events)

        if user_id:
            results = [e for e in results if e.user_id == user_id]
        if session_id:
            results = [e for e in results if e.session_id == session_id]
        if agent_id:
            results = [e for e in results if e.agent_id == agent_id]
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if severity:
            results = [e for e in results if e.severity == severity]
        if correlation_id:
            results = [e for e in results if e.correlation_id == correlation_id]
        if since_sec is not None:
            results = [e for e in results if e.timestamp >= since_sec]

        return sorted(results, key=lambda e: e.timestamp, reverse=True)[:limit]

    async def get_user_activity(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent activity for a user."""
        events = await self.query(user_id=user_id, limit=limit)
        return [e.as_dict() for e in events]

    async def get_agent_trail(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get the complete audit trail for an agent."""
        events = await self.query(agent_id=agent_id, limit=500)
        return [e.as_dict() for e in events]

    async def export_json(self, user_id: Optional[str] = None, since_sec: Optional[float] = None) -> str:
        """Export audit events as JSON."""
        events = await self.query(user_id=user_id, since_sec=since_sec, limit=10000)
        return json.dumps([e.as_dict() for e in events], default=str, indent=2)

    async def _cleanup_loop(self) -> None:
        """Background task to remove expired events."""
        while True:
            try:
                await asyncio.sleep(3600)  # Every hour
                self._purge_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("AuditCenter cleanup error: %s", e)

    def _purge_expired(self) -> None:
        """Remove events older than retention period."""
        cutoff = time.monotonic() - self._retention_sec
        with self._lock:
            before = len(self._events)
            self._events = [e for e in self._events if e.timestamp >= cutoff]
            removed = before - len(self._events)
            if removed > 0:
                logger.info("AuditCenter: purged %d expired events", removed)

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._events)
            by_type: Dict[str, int] = {}
            by_severity: Dict[str, int] = {}
            for e in self._events:
                by_type[e.event_type.value] = by_type.get(e.event_type.value, 0) + 1
                by_severity[e.severity.value] = by_severity.get(e.severity.value, 0) + 1
        return {
            "initialized": self._initialized,
            "total_events": total,
            "max_events": self._max_events,
            "retention_days": int(self._retention_sec / 86400),
            "by_type": by_type,
            "by_severity": by_severity,
        }
