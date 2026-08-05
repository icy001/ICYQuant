"""Diagnostic logging for service discovery resolution.

Provides ``ResolverDiagnostics`` which records resolution
history, routing decisions, and filtering actions for
debugging and observability.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_HISTORY = 1000
_MAX_ROUTING_LOG = 1000


class ResolverDiagnostics:
    """Records diagnostic information for service resolution.

    Maintains a bounded history of resolution attempts, routing
    decisions, and filtering actions for debugging and
    performance analysis.

    Usage::

        diag = ResolverDiagnostics()
        diag.record_resolution("payment", "round_robin", "inst-1", 0.003)
        history = diag.get_history("payment")
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._history: Deque[Dict[str, Any]] = deque(
            maxlen=_MAX_HISTORY
        )
        self._routing_log: Deque[Dict[str, Any]] = deque(
            maxlen=_MAX_ROUTING_LOG
        )
        self._filtering_log: Deque[Dict[str, Any]] = deque(
            maxlen=_MAX_HISTORY
        )
        self._resolution_count = 0
        self._routing_count = 0
        self._filtering_count = 0

    def record_resolution(
        self,
        service_name: str,
        strategy: str,
        selected_instance: str = None,
        latency: float = 0,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a service resolution attempt.

        Args:
            service_name: The resolved service name.
            strategy: The strategy used for selection.
            selected_instance: The selected instance ID.
            latency: Resolution latency in seconds.
            details: Additional diagnostic details.
        """
        entry: Dict[str, Any] = {
            "service_name": service_name,
            "strategy": strategy,
            "selected_instance": selected_instance,
            "latency": float(latency),
            "timestamp": time.time(),
            "details": dict(details) if details else {},
        }
        with self._lock:
            self._history.append(entry)
            self._resolution_count += 1

    def record_routing(
        self,
        route_type: str,
        service_name: str,
        decision: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a routing decision.

        Args:
            route_type: The type of routing applied.
            service_name: The service being routed.
            decision: The routing decision made.
            details: Additional decision details.
        """
        entry: Dict[str, Any] = {
            "route_type": route_type,
            "service_name": service_name,
            "decision": decision,
            "timestamp": time.time(),
            "details": dict(details) if details else {},
        }
        with self._lock:
            self._routing_log.append(entry)
            self._routing_count += 1

    def record_filtering(
        self,
        filter_type: str,
        service_name: str,
        removed: int,
        reason: str = "",
    ) -> None:
        """Record a filtering action.

        Args:
            filter_type: The type of filter applied.
            service_name: The service being filtered.
            removed: Number of instances removed.
            reason: Reason for removal.
        """
        entry: Dict[str, Any] = {
            "filter_type": filter_type,
            "service_name": service_name,
            "removed": int(removed),
            "reason": reason,
            "timestamp": time.time(),
        }
        with self._lock:
            self._filtering_log.append(entry)
            self._filtering_count += 1

    def get_history(
        self, service_name: str = None
    ) -> List[Dict[str, Any]]:
        """Retrieve resolution history.

        Args:
            service_name: If provided, filter history to this
                service.

        Returns:
            A list of resolution entries, most recent first.
        """
        with self._lock:
            entries = list(self._history)
        if service_name is not None:
            entries = [
                e for e in entries if e["service_name"] == service_name
            ]
        entries.reverse()
        return entries

    def get_routing_log(
        self, service_name: str = None
    ) -> List[Dict[str, Any]]:
        """Retrieve routing decision log.

        Args:
            service_name: If provided, filter log to this service.

        Returns:
            A list of routing entries, most recent first.
        """
        with self._lock:
            entries = list(self._routing_log)
        if service_name is not None:
            entries = [
                e for e in entries if e["service_name"] == service_name
            ]
        entries.reverse()
        return entries

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate a performance report from diagnostic data.

        Returns:
            A dictionary with aggregated performance metrics.
        """
        with self._lock:
            resolutions = list(self._history)
            routings = list(self._routing_log)
            filterings = list(self._filtering_log)

        total_resolutions = len(resolutions)
        total_routings = len(routings)
        total_filterings = len(filterings)

        latencies = [
            r["latency"]
            for r in resolutions
            if r.get("latency", 0) > 0
        ]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        max_latency = max(latencies) if latencies else 0.0

        by_strategy: Dict[str, int] = {}
        for r in resolutions:
            strategy = r.get("strategy", "unknown")
            by_strategy[strategy] = by_strategy.get(strategy, 0) + 1

        by_service: Dict[str, int] = {}
        for r in resolutions:
            svc = r.get("service_name", "unknown")
            by_service[svc] = by_service.get(svc, 0) + 1

        total_removed = sum(f.get("removed", 0) for f in filterings)

        return {
            "total_resolutions": total_resolutions,
            "total_routings": total_routings,
            "total_filterings": total_filterings,
            "avg_latency": avg_latency,
            "max_latency": max_latency,
            "by_strategy": by_strategy,
            "by_service": by_service,
            "total_filtered_removed": total_removed,
        }

    def clear(self, service_name: str = None) -> None:
        """Clear diagnostic history.

        Args:
            service_name: If provided, only clear entries for
                this service. If None, clear all history.
        """
        with self._lock:
            if service_name is None:
                self._history.clear()
                self._routing_log.clear()
                self._filtering_log.clear()
                logger.debug("Diagnostics cleared completely.")
            else:
                self._history = deque(
                    (
                        e
                        for e in self._history
                        if e["service_name"] != service_name
                    ),
                    maxlen=_MAX_HISTORY,
                )
                self._routing_log = deque(
                    (
                        e
                        for e in self._routing_log
                        if e["service_name"] != service_name
                    ),
                    maxlen=_MAX_ROUTING_LOG,
                )
                self._filtering_log = deque(
                    (
                        e
                        for e in self._filtering_log
                        if e["service_name"] != service_name
                    ),
                    maxlen=_MAX_HISTORY,
                )
                logger.debug(
                    "Diagnostics cleared for service '%s'.",
                    service_name,
                )

    def get_stats(self) -> Dict[str, Any]:
        """Return diagnostics statistics.

        Returns:
            A dictionary with counts and buffer sizes.
        """
        with self._lock:
            return {
                "diagnostics": "ResolverDiagnostics",
                "resolution_count": self._resolution_count,
                "routing_count": self._routing_count,
                "filtering_count": self._filtering_count,
                "history_size": len(self._history),
                "routing_log_size": len(self._routing_log),
                "filtering_log_size": len(self._filtering_log),
                "max_history": _MAX_HISTORY,
                "max_routing_log": _MAX_ROUTING_LOG,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"ResolverDiagnostics(resolutions={self._resolution_count}, "
                f"routings={self._routing_count})"
            )