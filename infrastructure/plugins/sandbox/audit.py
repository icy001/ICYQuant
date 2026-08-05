"""Sandbox audit logging.

Provides :class:`AuditLog` for recording and querying
security-relevant events within the sandbox environment.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AuditLog:
    """Records and queries sandbox security events.

    Captures a chronological log of all security-relevant events
    including sandbox creation, destruction, policy enforcement,
    violations, and access decisions.

    Attributes:
        _entries: List of audit log entries.
        _lock: Thread-safe reentrant lock.
        _max_entries: Maximum number of entries retained.
    """

    def __init__(self, max_entries: int = 50000) -> None:
        """Initialize the audit log.

        Args:
            max_entries: Maximum number of entries to retain
                (default: 50000).
        """
        self._entries: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        self._max_entries = max_entries

    def log_event(
        self,
        event_type: str,
        plugin_id: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "info",
    ) -> None:
        """Record an audit event.

        Args:
            event_type: The type of event (e.g.
                ``"sandbox_created"``, ``"permission_denied"``).
            plugin_id: The plugin involved.
            message: Human-readable description.
            details: Optional structured details.
            severity: Event severity (``info``, ``warning``,
                ``error``, ``critical``).
        """
        entry: Dict[str, Any] = {
            "timestamp": time.time(),
            "event_type": event_type,
            "plugin_id": plugin_id,
            "message": message,
            "severity": severity,
            "details": details or {},
        }
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]

        if severity in ("error", "critical"):
            logger.warning(
                "Audit [%s] %s: %s", plugin_id, event_type, message
            )

    def query(
        self,
        plugin_id: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query audit log entries with optional filters.

        Args:
            plugin_id: Filter by plugin ID.
            event_type: Filter by event type.
            severity: Filter by severity level.
            limit: Maximum number of entries to return
                (most recent first).

        Returns:
            A list of matching audit log entries.
        """
        with self._lock:
            results = []
            for entry in reversed(self._entries):
                if plugin_id and entry["plugin_id"] != plugin_id:
                    continue
                if event_type and entry["event_type"] != event_type:
                    continue
                if severity and entry["severity"] != severity:
                    continue
                results.append(entry)
                if len(results) >= limit:
                    break
            return results

    def get_recent(
        self, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get the most recent audit entries.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            A list of the most recent entries.
        """
        return self.query(limit=limit)

    def get_event_counts(
        self, plugin_id: Optional[str] = None
    ) -> Dict[str, int]:
        """Get event type counts, optionally filtered by plugin.

        Args:
            plugin_id: Optional plugin ID filter.

        Returns:
            A dictionary of event_type → count.
        """
        with self._lock:
            counts: Dict[str, int] = {}
            for entry in self._entries:
                if plugin_id and entry["plugin_id"] != plugin_id:
                    continue
                et = entry["event_type"]
                counts[et] = counts.get(et, 0) + 1
            return counts

    def clear(self) -> None:
        """Clear all audit log entries."""
        with self._lock:
            self._entries.clear()
            logger.info("Audit log cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get audit log statistics.

        Returns:
            A dictionary with ``total_entries``, ``max_entries``,
            and ``event_counts``.
        """
        with self._lock:
            return {
                "total_entries": len(self._entries),
                "max_entries": self._max_entries,
                "event_counts": self.get_event_counts(),
            }