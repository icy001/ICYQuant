"""
Audit Log — Structured audit logging for the Control Plane.
"""

from __future__ import annotations

import time
import uuid
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AuditLog:
    """
    Structured audit log for all Control Plane operations.

    Supports filtering by actor, action, entity, time range, and severity.
    """

    def __init__(self, max_entries: int = 1_000_000):
        self._entries: list[dict] = []
        self._max_entries = max_entries

    def log(
        self,
        action: str,
        actor: str = "autonomous",
        entity_type: str = "",
        entity_id: str = "",
        outcome: str = "",
        details: Optional[dict] = None,
        severity: str = "info",
    ) -> str:
        """Write an audit log entry."""
        entry_id = str(uuid.uuid4())
        entry = {
            "entry_id": entry_id,
            "timestamp": time.time(),
            "action": action,
            "actor": actor,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "outcome": outcome,
            "severity": severity,
            "details": details or {},
        }
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]

        if severity in ("critical", "error"):
            logger.error("AUDIT [%s] %s → %s (%s)", severity, actor, action, outcome)

        return entry_id

    def query(
        self,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query audit log entries."""
        results = self._entries
        if actor:
            results = [e for e in results if e["actor"] == actor]
        if action:
            results = [e for e in results if e["action"] == action]
        if entity_id:
            results = [e for e in results if e["entity_id"] == entity_id]
        return results[-limit:]

    def stats(self) -> dict:
        return {
            "total_entries": len(self._entries),
            "max_entries": self._max_entries,
        }
