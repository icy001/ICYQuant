"""Marketplace audit logging.

Provides :class:`MarketplaceAudit` for recording and querying
marketplace events such as installs, updates, uninstalls, rollbacks,
downloads, errors, and violations.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

VALID_EVENT_TYPES = {
    "install",
    "update",
    "uninstall",
    "rollback",
    "download",
    "error",
    "violation",
}


class MarketplaceAudit:
    """Records and queries marketplace audit events.

    Captures a chronological log of all marketplace events including
    installs, updates, uninstalls, rollbacks, downloads, errors,
    and violations.

    Attributes:
        _entries: List of audit log entries.
        _lock: Thread-safe reentrant lock.
        _max_entries: Maximum number of entries retained.
    """

    def __init__(self, max_entries: int = 50000) -> None:
        self._entries: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        self._max_entries = max_entries

    def log_event(
        self,
        event_type: str,
        plugin_id: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record an audit event.

        Args:
            event_type: The type of event (e.g. ``"install"``,
                ``"update"``, ``"error"``).
            plugin_id: The plugin involved.
            details: Optional structured details.
        """
        entry: Dict[str, Any] = {
            "timestamp": time.time(),
            "event_type": event_type,
            "plugin_id": plugin_id,
            "details": details or {},
        }
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]

        if event_type in ("error", "violation"):
            logger.warning(
                "Marketplace audit [%s] %s: %s",
                plugin_id,
                event_type,
                details or "",
            )

    def get_events(
        self,
        plugin_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieve audit events with optional filters.

        Args:
            plugin_id: Filter by plugin ID (``None`` = all plugins).
            event_type: Filter by event type (``None`` = all types).
            limit: Maximum number of entries to return (most recent
                first).

        Returns:
            A list of matching audit event dictionaries.
        """
        with self._lock:
            results: List[Dict[str, Any]] = []
            for entry in reversed(self._entries):
                if plugin_id and entry["plugin_id"] != plugin_id:
                    continue
                if event_type and entry["event_type"] != event_type:
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
        return self.get_events(limit=limit)

    def get_event_counts(
        self, plugin_id: Optional[str] = None
    ) -> Dict[str, int]:
        """Get event type counts, optionally filtered by plugin.

        Args:
            plugin_id: Optional plugin ID filter.

        Returns:
            A dictionary of event_type to count.
        """
        with self._lock:
            counts: Dict[str, int] = {}
            for entry in self._entries:
                if plugin_id and entry["plugin_id"] != plugin_id:
                    continue
                et = entry["event_type"]
                counts[et] = counts.get(et, 0) + 1
            return counts

    def query(
        self, filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Query audit events using a filter dictionary.

        Supported filter keys: ``plugin_id``, ``event_type``,
        ``min_timestamp``, ``max_timestamp``, ``limit``.

        Args:
            filters: Dictionary of filter criteria.

        Returns:
            A list of matching audit event dictionaries.
        """
        plugin_id = filters.get("plugin_id")
        event_type = filters.get("event_type")
        min_ts = filters.get("min_timestamp")
        max_ts = filters.get("max_timestamp")
        limit = filters.get("limit", 100)

        with self._lock:
            results: List[Dict[str, Any]] = []
            for entry in reversed(self._entries):
                if plugin_id and entry["plugin_id"] != plugin_id:
                    continue
                if event_type and entry["event_type"] != event_type:
                    continue
                ts = entry["timestamp"]
                if min_ts is not None and ts < min_ts:
                    continue
                if max_ts is not None and ts > max_ts:
                    continue
                results.append(entry)
                if len(results) >= limit:
                    break
            return results

    def clear(
        self, plugin_id: Optional[str] = None
    ) -> None:
        """Clear audit entries, optionally for a specific plugin.

        Args:
            plugin_id: Plugin ID to clear. When ``None``, clears all
                entries.
        """
        with self._lock:
            if plugin_id is None:
                self._entries.clear()
                logger.info("Marketplace audit log cleared")
            else:
                before = len(self._entries)
                self._entries = [
                    e
                    for e in self._entries
                    if e["plugin_id"] != plugin_id
                ]
                removed = before - len(self._entries)
                logger.debug(
                    "Cleared %d audit entries for plugin '%s'.",
                    removed,
                    plugin_id,
                )

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
                "tracked_plugins": len(
                    {e["plugin_id"] for e in self._entries}
                ),
            }