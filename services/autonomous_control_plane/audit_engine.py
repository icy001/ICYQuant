"""
Audit Engine — Complete audit trail for all autonomous decisions.

All autonomous decisions are audited with: who, what, why, when,
policy, model, input, output, risk, approval, and result.
"""

from __future__ import annotations

import uuid
import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AuditEngine:
    """
    Central audit engine for autonomous decisions.

    Records every decision with full context for regulatory compliance,
    performance analysis, and incident investigation.
    """

    def __init__(self, retention_days: int = 2555):
        self._retention_days = retention_days
        self._audit_log: list[dict] = []
        self._audit_count = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _init__(self):
        logger.info("AuditEngine initialized (retention=%d days)", self._retention_days)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    async def record(self, context) -> str:
        """Record an audit event for a decision context."""
        event_id = str(uuid.uuid4())
        entry = {
            "event_id": event_id,
            "timestamp": time.time(),
            "trace_id": getattr(context, "trace_id", ""),
            "decision_id": getattr(context, "decision_id", ""),
            "entity_type": getattr(context, "entity_type", ""),
            "entity_id": getattr(context, "entity_id", ""),
            "action": getattr(context, "action", ""),
            "outcome": getattr(context, "outcome", ""),
            "policy_id": getattr(context, "policy_id", ""),
            "autonomy_level": getattr(context, "autonomy_level", 0),
            "snapshot": context.snapshot() if hasattr(context, "snapshot") else {},
        }
        self._audit_log.append(entry)
        self._audit_count += 1
        self._enforce_retention()
        return event_id

    def record_event(self, event_type: str, details: dict):
        """Record a manual audit event."""
        self._audit_log.append({
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": time.time(),
            **details,
        })
        self._audit_count += 1
        self._enforce_retention()

    def _enforce_retention(self):
        """Remove entries older than retention period."""
        cutoff = time.time() - self._retention_days * 86400
        self._audit_log = [e for e in self._audit_log if e.get("timestamp", 0) > cutoff]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        entity_id: Optional[str] = None,
        event_type: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query audit log entries."""
        results = self._audit_log

        if entity_id:
            results = [e for e in results if e.get("entity_id") == entity_id]
        if event_type:
            results = [e for e in results if e.get("event_type") == event_type]
        if since:
            results = [e for e in results if e.get("timestamp", 0) >= since]

        return results[-limit:]

    def get_by_trace(self, trace_id: str) -> list[dict]:
        """Get all audit entries for a trace."""
        return [e for e in self._audit_log if e.get("trace_id") == trace_id]

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "total_events": self._audit_count,
            "current_entries": len(self._audit_log),
            "retention_days": self._retention_days,
        }
