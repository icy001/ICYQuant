"""Plugin diagnostics for debugging.

Provides structured diagnostic information for the ICYQuant plugin
framework, tracking state transitions, performance metrics, config
changes, dependency status, and error history.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticInfo:
    """A single diagnostic event for a plugin."""

    plugin_id: str
    category: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the diagnostic info to a dictionary."""
        return {
            "plugin_id": self.plugin_id,
            "category": self.category,
            "message": self.message,
            "details": dict(self.details),
            "timestamp": self.timestamp,
        }


class PluginDiagnostics:
    """Provides diagnostic information for plugins.

    Maintains a bounded history of diagnostic events across five
    categories: state transitions, performance metrics, configuration
    changes, dependency status, and error history.
    """

    def __init__(self, max_history: int = 1000) -> None:
        self._max_history = max_history
        self._history: List[DiagnosticInfo] = []
        self._plugin_index: Dict[str, List[int]] = defaultdict(list)
        self._category_index: Dict[str, List[int]] = defaultdict(list)
        self._counters: Dict[str, int] = defaultdict(int)
        self._perf_data: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def record(self, info: DiagnosticInfo) -> None:
        """Record a diagnostic event.

        Args:
            info: The diagnostic information to record.
        """
        idx = len(self._history)
        self._history.append(info)
        self._plugin_index[info.plugin_id].append(idx)
        self._category_index[info.category].append(idx)
        self._counters[info.category] += 1

        if info.category == "performance":
            self._perf_data[info.plugin_id].append(
                {
                    "operation": info.message,
                    "duration_ms": info.details.get("duration_ms", 0.0),
                    "timestamp": info.timestamp,
                }
            )

        self._trim_history()

    def record_state_change(self, plugin_id: str, old: str, new: str) -> None:
        """Record a plugin state transition.

        Args:
            plugin_id: The unique plugin identifier.
            old: Previous lifecycle state.
            new: New lifecycle state.
        """
        self.record(
            DiagnosticInfo(
                plugin_id=plugin_id,
                category="state",
                message=f"State change: {old} -> {new}",
                details={"old_state": old, "new_state": new},
            )
        )

    def record_performance(
        self, plugin_id: str, operation: str, duration_ms: float
    ) -> None:
        """Record a performance measurement.

        Args:
            plugin_id: The unique plugin identifier.
            operation: The operation being measured.
            duration_ms: Duration in milliseconds.
        """
        self.record(
            DiagnosticInfo(
                plugin_id=plugin_id,
                category="performance",
                message=operation,
                details={
                    "duration_ms": duration_ms,
                    "operation": operation,
                },
            )
        )

    def record_config_change(
        self, plugin_id: str, key: str, old_value: Any, new_value: Any
    ) -> None:
        """Record a configuration change for a plugin.

        Args:
            plugin_id: The unique plugin identifier.
            key: Configuration key that changed.
            old_value: Previous value.
            new_value: New value.
        """
        self.record(
            DiagnosticInfo(
                plugin_id=plugin_id,
                category="config",
                message=f"Config key '{key}' changed.",
                details={
                    "key": key,
                    "old_value": str(old_value) if old_value is not None else None,
                    "new_value": str(new_value) if new_value is not None else None,
                },
            )
        )

    def record_error(
        self, plugin_id: str, error: str, stack: str = ""
    ) -> None:
        """Record a plugin error.

        Args:
            plugin_id: The unique plugin identifier.
            error: Error message.
            stack: Optional stack trace.
        """
        self.record(
            DiagnosticInfo(
                plugin_id=plugin_id,
                category="error",
                message=error,
                details={
                    "error": error,
                    "stack": stack,
                },
            )
        )

    def get_diagnostics(
        self,
        plugin_id: str = "",
        category: str = "",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieve diagnostic events with optional filtering.

        Args:
            plugin_id: Filter by plugin ID (empty = all plugins).
            category: Filter by category (empty = all categories).
            limit: Maximum number of results to return.

        Returns:
            List of diagnostic entries as dictionaries, most recent first.
        """
        indices: set = set()

        if plugin_id and category:
            plugin_indices = set(self._plugin_index.get(plugin_id, []))
            category_indices = set(self._category_index.get(category, []))
            indices = plugin_indices & category_indices
        elif plugin_id:
            indices = set(self._plugin_index.get(plugin_id, []))
        elif category:
            indices = set(self._category_index.get(category, []))
        else:
            indices = set(range(len(self._history)))

        sorted_indices = sorted(indices, reverse=True)
        results: List[Dict[str, Any]] = []
        for idx in sorted_indices:
            if idx < len(self._history):
                results.append(self._history[idx].to_dict())
                if len(results) >= limit:
                    break
        return results

    def get_error_history(
        self, plugin_id: str = "", limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Retrieve error history for a plugin or all plugins.

        Args:
            plugin_id: Filter by plugin ID (empty = all plugins).
            limit: Maximum number of results to return.

        Returns:
            List of error diagnostic entries, most recent first.
        """
        return self.get_diagnostics(
            plugin_id=plugin_id, category="error", limit=limit
        )

    def get_performance_report(
        self, plugin_id: str = ""
    ) -> Dict[str, Any]:
        """Generate a performance report for a plugin or all plugins.

        Args:
            plugin_id: Plugin ID to report on (empty = all plugins).

        Returns:
            Dictionary with performance statistics.
        """
        if plugin_id:
            plugins = {plugin_id: self._perf_data.get(plugin_id, [])}
        else:
            plugins = dict(self._perf_data)

        plugin_reports: Dict[str, Any] = {}
        for pid, entries in plugins.items():
            if not entries:
                plugin_reports[pid] = {
                    "total_operations": 0,
                    "avg_duration_ms": 0.0,
                    "min_duration_ms": 0.0,
                    "max_duration_ms": 0.0,
                    "operations": {},
                }
                continue
            durations = [e["duration_ms"] for e in entries]
            op_counts: Dict[str, int] = defaultdict(int)
            for e in entries:
                op_counts[e["operation"]] += 1

            plugin_reports[pid] = {
                "total_operations": len(entries),
                "avg_duration_ms": sum(durations) / len(durations),
                "min_duration_ms": min(durations),
                "max_duration_ms": max(durations),
                "operations": dict(op_counts),
            }

        return {
            "timestamp": time.time(),
            "plugins": plugin_reports,
        }

    def clear(self, plugin_id: str = "") -> None:
        """Clear diagnostic history, optionally for a specific plugin.

        Args:
            plugin_id: Plugin ID to clear (empty = clear all).
        """
        if not plugin_id:
            self._history.clear()
            self._plugin_index.clear()
            self._category_index.clear()
            self._counters.clear()
            self._perf_data.clear()
            logger.info("All diagnostics cleared.")
            return

        indices_to_remove = set(self._plugin_index.get(plugin_id, []))
        if not indices_to_remove:
            return

        new_history: List[DiagnosticInfo] = []
        for idx, entry in enumerate(self._history):
            if idx not in indices_to_remove:
                new_history.append(entry)

        self._history = new_history
        self._rebuild_indexes()

        self._perf_data.pop(plugin_id, None)
        self._plugin_index.pop(plugin_id, None)

        logger.info("Diagnostics cleared for plugin '%s'.", plugin_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get summary statistics of the diagnostics system.

        Returns:
            Dictionary with counts and category breakdown.
        """
        return {
            "total_entries": len(self._history),
            "max_history": self._max_history,
            "by_category": dict(self._counters),
            "tracked_plugins": len(self._plugin_index),
            "plugin_ids": list(self._plugin_index.keys()),
            "perf_tracked_plugins": len(self._perf_data),
        }

    def _trim_history(self) -> None:
        """Trim history to the configured maximum size."""
        if len(self._history) > self._max_history:
            excess = len(self._history) - self._max_history
            self._history = self._history[excess:]
            self._rebuild_indexes()

    def _rebuild_indexes(self) -> None:
        """Rebuild all indexes from the history list."""
        self._plugin_index.clear()
        self._category_index.clear()
        self._counters.clear()
        self._perf_data.clear()

        for idx, entry in enumerate(self._history):
            self._plugin_index[entry.plugin_id].append(idx)
            self._category_index[entry.category].append(idx)
            self._counters[entry.category] += 1

            if entry.category == "performance":
                self._perf_data[entry.plugin_id].append(
                    {
                        "operation": entry.message,
                        "duration_ms": entry.details.get("duration_ms", 0.0),
                        "timestamp": entry.timestamp,
                    }
                )