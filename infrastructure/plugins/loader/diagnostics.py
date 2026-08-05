"""Loader diagnostics for the plugin loader subsystem.

Provides structured diagnostic event tracking for loader components,
recording state changes, errors, performance measurements, and load
step events with timestamps and contextual details.

The diagnostics history is bounded to ``max_history`` entries, with
the oldest entries dropped when the bound is exceeded.
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
class _DiagnosticEvent:
    """A single diagnostic event recorded by the loader.

    Attributes:
        timestamp: Event time as a Unix timestamp (seconds).
        plugin_id: Plugin id (or ``""`` for global events).
        event_type: Category of the event (e.g. ``"state_change"``,
            ``"error"``, ``"performance"``, ``"load_step"``).
        message: Human-readable event description.
        details: Optional contextual details.
    """

    timestamp: float
    plugin_id: str
    event_type: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the event to a dictionary."""
        return {
            "timestamp": self.timestamp,
            "plugin_id": self.plugin_id,
            "event_type": self.event_type,
            "message": self.message,
            "details": dict(self.details),
        }


class LoaderDiagnostics:
    """Records and queries loader diagnostic events.

    Maintains a bounded history of events with counters indexed by
    event type. Thread-safe via a single lock.

    Attributes:
        max_history: Maximum number of events retained.
    """

    def __init__(self, max_history: int = 2000) -> None:
        self._history: List[_DiagnosticEvent] = []
        self._max_history = max_history
        self._counters: Dict[str, int] = defaultdict(int)
        self._performance_data: Dict[str, List[Dict[str, Any]]] = (
            defaultdict(list)
        )
        self._lock = threading.Lock()

    def record_state_change(
        self, plugin_id: str, old_state: str, new_state: str
    ) -> None:
        """Record a plugin state transition.

        Args:
            plugin_id: The plugin identifier.
            old_state: The previous state name.
            new_state: The new state name.
        """
        now = time.time()
        self._record(
            plugin_id=plugin_id,
            event_type="state_change",
            message=(
                f"Plugin '{plugin_id}' state changed: "
                f"{old_state} -> {new_state}"
            ),
            details={
                "old_state": old_state,
                "new_state": new_state,
            },
        )

    def record_error(
        self,
        plugin_id: str,
        error: str,
        traceback: str = "",
    ) -> None:
        """Record a loader error event.

        Args:
            plugin_id: The plugin identifier.
            error: Error message or description.
            traceback: Optional traceback string.
        """
        self._record(
            plugin_id=plugin_id,
            event_type="error",
            message=f"Error for plugin '{plugin_id}': {error}",
            details={
                "error": error,
                "traceback": traceback,
            },
        )

    def record_performance(
        self, plugin_id: str, operation: str, duration_ms: float
    ) -> None:
        """Record a performance measurement for an operation.

        Args:
            plugin_id: The plugin identifier.
            operation: The operation name (e.g. ``"load"``, ``"scan"``).
            duration_ms: Duration of the operation in milliseconds.
        """
        now = time.time()
        self._record(
            plugin_id=plugin_id,
            event_type="performance",
            message=(
                f"Performance: {operation} for '{plugin_id}' "
                f"took {duration_ms:.2f}ms"
            ),
            details={
                "operation": operation,
                "duration_ms": duration_ms,
            },
        )

        with self._lock:
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

    def record_load_step(
        self,
        plugin_id: str,
        step: str,
        success: bool,
        duration: float,
    ) -> None:
        """Record a single step during plugin loading.

        Args:
            plugin_id: The plugin identifier.
            step: The step name (e.g. ``"validate"``, ``"import"``,
                ``"instantiate"``).
            success: Whether the step succeeded.
            duration: Duration of the step in seconds.
        """
        status = "succeeded" if success else "failed"
        self._record(
            plugin_id=plugin_id,
            event_type="load_step",
            message=(
                f"Load step '{step}' for '{plugin_id}' {status} "
                f"in {duration:.4f}s"
            ),
            details={
                "step": step,
                "success": success,
                "duration": duration,
            },
        )

    def get_diagnostics(
        self, plugin_id: str = ""
    ) -> List[Dict[str, Any]]:
        """Retrieve diagnostic events with optional plugin filter.

        Args:
            plugin_id: Filter by plugin id (empty = all plugins).

        Returns:
            List of events as dictionaries, most recent first.
        """
        with self._lock:
            results: List[Dict[str, Any]] = []
            for event in reversed(self._history):
                if plugin_id and event.plugin_id != plugin_id:
                    continue
                results.append(event.to_dict())
            return results

    def get_error_history(
        self, plugin_id: str = ""
    ) -> List[Dict[str, Any]]:
        """Retrieve error history for a plugin or all plugins.

        Args:
            plugin_id: Filter by plugin id (empty = all plugins).

        Returns:
            List of error event dictionaries, most recent first.
        """
        with self._lock:
            results: List[Dict[str, Any]] = []
            for event in reversed(self._history):
                if event.event_type != "error":
                    continue
                if plugin_id and event.plugin_id != plugin_id:
                    continue
                results.append(event.to_dict())
            return results

    def get_performance_report(
        self, plugin_id: str = ""
    ) -> Dict[str, Any]:
        """Generate a performance report for a plugin or all plugins.

        Args:
            plugin_id: Filter by plugin id (empty = all plugins).

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

    def clear(self, plugin_id: str = "") -> None:
        """Clear diagnostic history, optionally for a specific plugin.

        Args:
            plugin_id: Plugin id to clear. When empty, clears all
                history.
        """
        with self._lock:
            if not plugin_id:
                self._history.clear()
                self._counters.clear()
                self._performance_data.clear()
                logger.debug("All loader diagnostics cleared.")
                return

            self._history = [
                e for e in self._history if e.plugin_id != plugin_id
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
                "Loader diagnostics cleared for plugin '%s'.",
                plugin_id,
            )

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the diagnostics system.

        Returns:
            A dictionary with total entries, max history, and event
            type counts.
        """
        with self._lock:
            return {
                "total_entries": len(self._history),
                "max_history": self._max_history,
                "by_event_type": dict(self._counters),
                "tracked_plugins": len(
                    {e.plugin_id for e in self._history}
                ),
            }

    def _record(
        self,
        plugin_id: str,
        event_type: str,
        message: str,
        details: Dict[str, Any],
    ) -> None:
        """Record a diagnostic event (internal)."""
        event = _DiagnosticEvent(
            timestamp=time.time(),
            plugin_id=plugin_id,
            event_type=event_type,
            message=message,
            details=details,
        )
        with self._lock:
            self._history.append(event)
            self._counters[event_type] += 1
            if len(self._history) > self._max_history:
                excess = len(self._history) - self._max_history
                self._history = self._history[excess:]

    def _rebuild_counters(self) -> None:
        """Rebuild event type counters from history."""
        self._counters.clear()
        for event in self._history:
            self._counters[event.event_type] += 1