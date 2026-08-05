"""Service discovery diagnostics for debugging.

Provides structured diagnostic information for the ICYQuant service
discovery subsystem, tracking operations, errors, and performance
metrics with bounded, indexed history.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ServiceDiscoveryDiagnostics:
    """Provides diagnostic information for service discovery.

    Maintains a bounded history of operation and error events indexed
    by service name, enabling efficient queries for diagnostics,
    error history, operation logs, and performance reports.
    """

    def __init__(self, max_history: int = 1000) -> None:
        self._max_history = max_history
        self._history: List[Dict[str, Any]] = []
        self._service_index: Dict[str, List[int]] = defaultdict(list)
        self._category_index: Dict[str, List[int]] = defaultdict(list)
        self._counters: Dict[str, int] = defaultdict(int)
        self._perf_data: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def record_operation(
        self,
        operation: str,
        service_name: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a service discovery operation.

        Args:
            operation: The operation being performed (e.g. register).
            service_name: The logical service name.
            status: Outcome status (e.g. success, failure).
            details: Optional additional details.
        """
        entry = {
            "category": "operation",
            "operation": operation or "unknown",
            "service_name": service_name or "",
            "status": status or "unknown",
            "details": dict(details) if details else {},
            "timestamp": time.time(),
        }
        self._append(entry)

    def record_error(
        self,
        service_name: str,
        error: str,
        operation: str = "",
        traceback: str = "",
    ) -> None:
        """Record a service discovery error.

        Args:
            service_name: The logical service name.
            error: Error message.
            operation: Optional operation during which the error occurred.
            traceback: Optional stack trace.
        """
        entry = {
            "category": "error",
            "operation": operation or "",
            "service_name": service_name or "",
            "status": "error",
            "error": error,
            "traceback": traceback,
            "details": {"error": error, "operation": operation},
            "timestamp": time.time(),
        }
        self._append(entry)
        logger.warning(
            "Service discovery error for '%s' (%s): %s",
            service_name,
            operation or "unknown",
            error,
        )

    def get_diagnostics(
        self, service_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve diagnostic events, optionally filtered by service.

        Args:
            service_name: Filter by service name (None = all).

        Returns:
            List of diagnostic entries, most recent first.
        """
        with self._index_view() as indices:
            results = self._collect(indices, limit=self._max_history)
        if service_name is not None:
            results = [r for r in results if r.get("service_name") == service_name]
        return results

    def get_error_history(
        self, service_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve error history, optionally filtered by service."""
        with self._index_view(category="error") as indices:
            results = self._collect(indices, limit=self._max_history)
        if service_name is not None:
            results = [r for r in results if r.get("service_name") == service_name]
        return results

    def get_operation_log(
        self, service_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve operation log, optionally filtered by service."""
        with self._index_view(category="operation") as indices:
            results = self._collect(indices, limit=self._max_history)
        if service_name is not None:
            results = [r for r in results if r.get("service_name") == service_name]
        return results

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate a performance report across tracked services.

        Returns:
            Dictionary with per-service performance statistics
            aggregated from operation durations recorded in details.
        """
        reports: Dict[str, Any] = {}
        for service_name, entries in self._perf_data.items():
            durations = [
                e.get("duration", 0.0)
                for e in entries
                if e.get("duration") is not None
            ]
            op_counts: Dict[str, int] = defaultdict(int)
            for e in entries:
                op_counts[e.get("operation", "unknown")] += 1
            if not durations:
                reports[service_name] = {
                    "total_operations": len(entries),
                    "avg_duration": 0.0,
                    "min_duration": 0.0,
                    "max_duration": 0.0,
                    "operations": dict(op_counts),
                }
                continue
            reports[service_name] = {
                "total_operations": len(entries),
                "avg_duration": sum(durations) / len(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "operations": dict(op_counts),
            }
        return {
            "timestamp": time.time(),
            "services": reports,
        }

    def clear(self, service_name: Optional[str] = None) -> None:
        """Clear diagnostic history, optionally for a specific service."""
        if service_name is None:
            self._history.clear()
            self._service_index.clear()
            self._category_index.clear()
            self._counters.clear()
            self._perf_data.clear()
            logger.info("All service discovery diagnostics cleared.")
            return

        indices_to_remove = set(self._service_index.get(service_name, []))
        if not indices_to_remove:
            return
        new_history: List[Dict[str, Any]] = [
            entry
            for idx, entry in enumerate(self._history)
            if idx not in indices_to_remove
        ]
        self._history = new_history
        self._rebuild_indexes()
        self._perf_data.pop(service_name, None)
        logger.info("Diagnostics cleared for service '%s'.", service_name)

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics of the diagnostics system."""
        return {
            "total_entries": len(self._history),
            "max_history": self._max_history,
            "by_category": dict(self._counters),
            "tracked_services": len(self._service_index),
            "service_names": list(self._service_index.keys()),
            "perf_tracked_services": len(self._perf_data),
        }

    # ── Internal helpers ──

    def _append(self, entry: Dict[str, Any]) -> None:
        idx = len(self._history)
        self._history.append(entry)
        service_name = entry.get("service_name", "")
        category = entry.get("category", "")
        self._service_index[service_name].append(idx)
        self._category_index[category].append(idx)
        self._counters[category] += 1

        if category == "operation":
            details = entry.get("details", {}) or {}
            duration = details.get("duration", details.get("duration_ms"))
            if duration is not None:
                self._perf_data[service_name].append(
                    {
                        "operation": entry.get("operation", ""),
                        "duration": float(duration),
                        "timestamp": entry.get("timestamp", time.time()),
                    }
                )

        self._trim_history()

    def _trim_history(self) -> None:
        if len(self._history) > self._max_history:
            excess = len(self._history) - self._max_history
            self._history = self._history[excess:]
            self._rebuild_indexes()

    def _rebuild_indexes(self) -> None:
        self._service_index.clear()
        self._category_index.clear()
        self._counters.clear()
        self._perf_data.clear()

        for idx, entry in enumerate(self._history):
            service_name = entry.get("service_name", "")
            category = entry.get("category", "")
            self._service_index[service_name].append(idx)
            self._category_index[category].append(idx)
            self._counters[category] += 1

            if category == "operation":
                details = entry.get("details", {}) or {}
                duration = details.get("duration", details.get("duration_ms"))
                if duration is not None:
                    self._perf_data[service_name].append(
                        {
                            "operation": entry.get("operation", ""),
                            "duration": float(duration),
                            "timestamp": entry.get("timestamp", time.time()),
                        }
                    )

    class _IndexView:
        """Context manager yielding a snapshot of matching indices."""

        def __init__(
            self,
            outer: ServiceDiscoveryDiagnostics,
            service_name: Optional[str] = None,
            category: Optional[str] = None,
        ) -> None:
            self._outer = outer
            self._service_name = service_name
            self._category = category
            self._indices: set = set()

        def __enter__(self) -> set:
            outer = self._outer
            if self._service_name and self._category:
                service_set = set(
                    outer._service_index.get(self._service_name, [])
                )
                category_set = set(
                    outer._category_index.get(self._category, [])
                )
                self._indices = service_set & category_set
            elif self._service_name:
                self._indices = set(
                    outer._service_index.get(self._service_name, [])
                )
            elif self._category:
                self._indices = set(
                    outer._category_index.get(self._category, [])
                )
            else:
                self._indices = set(range(len(outer._history)))
            return self._indices

        def __exit__(self, *exc: Any) -> None:
            self._indices.clear()

    def _index_view(
        self,
        service_name: Optional[str] = None,
        category: Optional[str] = None,
    ) -> ServiceDiscoveryDiagnostics._IndexView:
        return self._IndexView(self, service_name=service_name, category=category)

    def _collect(self, indices: set, limit: int) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for idx in sorted(indices, reverse=True):
            if idx < len(self._history):
                results.append(dict(self._history[idx]))
                if len(results) >= limit:
                    break
        return results
