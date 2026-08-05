"""Marketplace diagnostics.

Provides :class:`MarketplaceDiagnostics` for structured diagnostic
event tracking of marketplace operations, recording state changes,
errors, performance measurements, and operation logs with
timestamps and contextual details.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class _DiagnosticEntry:
    """A single diagnostic entry recorded by the marketplace."""

    timestamp: float
    plugin_id: str
    operation: str
    status: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the entry to a dictionary."""
        return {
            "timestamp": self.timestamp,
            "plugin_id": self.plugin_id,
            "operation": self.operation,
            "status": self.status,
            "details": dict(self.details),
        }


class MarketplaceDiagnostics:
    """Records and queries marketplace diagnostic events.

    Maintains a bounded history of events with counters indexed
    by operation type.  Thread-safe via a single lock.

    Attributes:
        max_history: Maximum number of events retained.
    """

    def __init__(self, max_history: int = 2000) -> None:
        self._history: List[_DiagnosticEntry] = []
        self._max_history = max_history
        self._counters: Dict[str, int] = defaultdict(int)
        self._performance_data: Dict[str, List[Dict[str, Any]]] = (
            defaultdict(list)
        )
        self._lock = threading.Lock()

    def record_operation(
        self,
        operation: str,
        plugin_id: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a marketplace operation.

        Args:
            operation: The operation name (e.g. ``"install"``,
                ``"update"``, ``"download"``).
            plugin_id: The plugin identifier.
            status: The operation outcome (e.g. ``"success"``,
                ``"failure"``).
            details: Optional contextual details.
        """
        entry = _DiagnosticEntry(
            timestamp=time.time(),
            plugin_id=plugin_id,
            operation=operation,
            status=status,
            details=details or {},
        )
        with self._lock:
            self._history.append(entry)
            self._counters[operation] += 1
            if len(self._history) > self._max_history:
                excess = len(self._history) - self._max_history
                self._history = self._history[excess:]

    def record_error(
        self,
        plugin_id: str,
        error: str,
        operation: str = "",
        traceback: str = "",
    ) -> None:
        """Record a marketplace error event.

        Args:
            plugin_id: The plugin identifier.
            error: Error message or description.
            operation: The operation during which the error occurred.
            traceback: Optional traceback string.
        """
        entry = _DiagnosticEntry(
            timestamp=time.time(),
            plugin_id=plugin_id,
            operation=operation or "error",
            status="error",
            details={
                "error": error,
                "traceback": traceback,
            },
        )
        with self._lock:
            self._history.append(entry)
            self._counters["error"] += 1
            if len(self._history) > self._max_history:
                excess = len(self._history) - self._max_history
                self._history = self._history[excess:]

    def get_diagnostics(
        self, plugin_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve diagnostic entries with optional plugin filter.

        Args:
            plugin_id: Filter by plugin id (``None`` = all plugins).

        Returns:
            List of entries as dictionaries, most recent first.
        """
        with self._lock:
            results: List[Dict[str, Any]] = []
            for entry in reversed(self._history):
                if plugin_id and entry.plugin_id != plugin_id:
                    continue
                results.append(entry.to_dict())
            return results

    def get_error_history(
        self, plugin_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve error history for a plugin or all plugins.

        Args:
            plugin_id: Filter by plugin id (``None`` = all plugins).

        Returns:
            List of error event dictionaries, most recent first.
        """
        with self._lock:
            results: List[Dict[str, Any]] = []
            for entry in reversed(self._history):
                if entry.status != "error":
                    continue
                if plugin_id and entry.plugin_id != plugin_id:
                    continue
                results.append(entry.to_dict())
            return results

    def get_operation_log(
        self, plugin_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve the operation log for a plugin or all plugins.

        Args:
            plugin_id: Filter by plugin id (``None`` = all plugins).

        Returns:
            List of operation event dictionaries, most recent first.
        """
        with self._lock:
            results: List[Dict[str, Any]] = []
            for entry in reversed(self._history):
                if plugin_id and entry.plugin_id != plugin_id:
                    continue
                results.append(entry.to_dict())
            return results

    def get_performance_report(
        self, plugin_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a performance report for a plugin or all plugins.

        Args:
            plugin_id: Filter by plugin id (``None`` = all plugins).

        Returns:
            A dictionary with performance statistics grouped by
            operation name.
        """
        with self._lock:
            report: Dict[str, Any] = {}
            for key, entries in self._performance_data.items():
                pid, operation = key.split(":", 1)
                if plugin_id and pid != plugin_id:
                    continue
                if not entries:
                    continue
                durations = [e["duration_ms"] for e in entries]
                report[operation] = {
                    "count": len(durations),
                    "avg_ms": sum(durations) / len(durations),
                    "min_ms": min(durations),
                    "max_ms": max(durations),
                    "latest_ms": durations[-1],
                }
            return report

    def record_performance(
        self,
        plugin_id: str,
        operation: str,
        duration_ms: float,
    ) -> None:
        """Record a performance measurement for an operation.

        Args:
            plugin_id: The plugin identifier.
            operation: The operation name (e.g. ``"install"``,
                ``"download"``).
            duration_ms: Duration of the operation in milliseconds.
        """
        now = time.time()
        entry = _DiagnosticEntry(
            timestamp=now,
            plugin_id=plugin_id,
            operation=operation,
            status="performance",
            details={
                "duration_ms": duration_ms,
            },
        )
        with self._lock:
            self._history.append(entry)
            self._counters[operation] += 1
            if len(self._history) > self._max_history:
                excess = len(self._history) - self._max_history
                self._history = self._history[excess:]

            key = f"{plugin_id}:{operation}"
            self._performance_data[key].append({
                "timestamp": now,
                "duration_ms": duration_ms,
            })
            if len(self._performance_data[key]) > 1000:
                excess = len(self._performance_data[key]) - 1000
                self._performance_data[key] = self._performance_data[
                    key
                ][excess:]

    def clear(
        self, plugin_id: Optional[str] = None
    ) -> None:
        """Clear diagnostic history, optionally for a specific plugin.

        Args:
            plugin_id: Plugin id to clear. When ``None``, clears all
                history.
        """
        with self._lock:
            if plugin_id is None:
                self._history.clear()
                self._counters.clear()
                self._performance_data.clear()
                logger.debug("All marketplace diagnostics cleared.")
                return

            self._history = [
                e
                for e in self._history
                if e.plugin_id != plugin_id
            ]
            self._rebuild_counters()

            keys_to_remove = [
                k
                for k in self._performance_data
                if k.startswith(f"{plugin_id}:")
            ]
            for key in keys_to_remove:
                del self._performance_data[key]

            logger.debug(
                "Marketplace diagnostics cleared for plugin '%s'.",
                plugin_id,
            )

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the diagnostics system.

        Returns:
            A dictionary with total entries, max history, and
            operation type counts.
        """
        with self._lock:
            return {
                "total_entries": len(self._history),
                "max_history": self._max_history,
                "by_operation": dict(self._counters),
                "tracked_plugins": len(
                    {e.plugin_id for e in self._history}
                ),
            }

    def _rebuild_counters(self) -> None:
        """Rebuild operation counters from history."""
        self._counters.clear()
        for entry in self._history:
            self._counters[entry.operation] += 1
