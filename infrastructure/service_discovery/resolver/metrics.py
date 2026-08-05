"""Metrics collection for service discovery resolution.

Provides ``ResolverMetrics`` which records and aggregates
metrics for service resolution, routing, load balancing,
canary, version, locality, and consistent hash operations.

Metric names follow the ``icyquant_*`` naming convention.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

METRIC_RESOLVE_TOTAL = "icyquant_service_resolve_total"
METRIC_ROUTE_LATENCY = "icyquant_service_route_latency_seconds"
METRIC_LOAD_BALANCE_TOTAL = "icyquant_load_balance_total"
METRIC_CANARY_ROUTE_TOTAL = "icyquant_canary_route_total"
METRIC_VERSION_ROUTE_TOTAL = "icyquant_version_route_total"
METRIC_LOCALITY_ROUTE_TOTAL = "icyquant_locality_route_total"
METRIC_CONSISTENT_HASH_TOTAL = "icyquant_consistent_hash_total"


class ResolverMetrics:
    """Collects and aggregates resolver metrics.

    Supports counters, gauges, and histograms for tracking
    the performance and behavior of the service resolver.

    Usage::

        metrics = ResolverMetrics()
        metrics.record_resolve("payment", "round_robin", 0.005, True)
        snapshot = metrics.snapshot()
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: Dict[str, Dict[str, int]] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, Dict[str, float]] = {}
        self._timers: Dict[str, list] = {
            METRIC_ROUTE_LATENCY: [],
        }

    def record_resolve(
        self,
        service_name: str,
        strategy: str,
        duration: float,
        success: bool,
    ) -> None:
        """Record a service resolution attempt.

        Args:
            service_name: The resolved service name.
            strategy: The load balancing strategy used.
            duration: Resolution duration in seconds.
            success: Whether the resolution was successful.
        """
        self._increment_counter(
            METRIC_RESOLVE_TOTAL,
            {
                "service": service_name,
                "strategy": strategy,
                "status": "success" if success else "failure",
            },
        )
        self._record_timer(METRIC_ROUTE_LATENCY, duration)
        logger.debug(
            "resolve: service=%s strategy=%s duration=%.4f success=%s",
            service_name,
            strategy,
            duration,
            success,
        )

    def record_route(self, route_type: str, latency: float) -> None:
        """Record a routing decision latency.

        Args:
            route_type: The type of routing (e.g., "version",
                "canary", "health").
            latency: Routing latency in seconds.
        """
        self._increment_counter(
            "icyquant_route_total",
            {"route_type": route_type},
        )
        self._record_timer(METRIC_ROUTE_LATENCY, latency)
        logger.debug(
            "route: type=%s latency=%.4f", route_type, latency
        )

    def record_load_balance(
        self, strategy: str, success: bool
    ) -> None:
        """Record a load balancing decision.

        Args:
            strategy: The load balancing strategy used.
            success: Whether the selection was successful.
        """
        self._increment_counter(
            METRIC_LOAD_BALANCE_TOTAL,
            {
                "strategy": strategy,
                "status": "success" if success else "failure",
            },
        )

    def record_canary_route(
        self, service_name: str, is_canary: bool
    ) -> None:
        """Record a canary routing decision.

        Args:
            service_name: The service being resolved.
            is_canary: Whether the request went to canary.
        """
        self._increment_counter(
            METRIC_CANARY_ROUTE_TOTAL,
            {
                "service": service_name,
                "route": "canary" if is_canary else "normal",
            },
        )

    def record_version_route(
        self, service_name: str, version: str
    ) -> None:
        """Record a version-based routing decision.

        Args:
            service_name: The service being resolved.
            version: The version selected.
        """
        self._increment_counter(
            METRIC_VERSION_ROUTE_TOTAL,
            {"service": service_name, "version": version},
        )

    def record_locality_route(
        self, service_name: str, locality: str
    ) -> None:
        """Record a locality-based routing decision.

        Args:
            service_name: The service being resolved.
            locality: The locality selected (e.g., "region",
                "zone", "fallback").
        """
        self._increment_counter(
            METRIC_LOCALITY_ROUTE_TOTAL,
            {"service": service_name, "locality": locality},
        )

    def record_consistent_hash(
        self, service_name: str, success: bool
    ) -> None:
        """Record a consistent hash routing decision.

        Args:
            service_name: The service being resolved.
            success: Whether the hash routing was successful.
        """
        self._increment_counter(
            METRIC_CONSISTENT_HASH_TOTAL,
            {
                "service": service_name,
                "status": "success" if success else "failure",
            },
        )

    def snapshot(self) -> Dict[str, Any]:
        """Return a point-in-time metrics snapshot.

        Returns:
            A dictionary with all metric values and aggregates.
        """
        with self._lock:
            snapshot_data: Dict[str, Any] = {}

            for name, labels in self._counters.items():
                for label_key, count in labels.items():
                    metric_key = f"{name}{label_key}"
                    snapshot_data[metric_key] = count

            for name, values in self._timers.items():
                if values:
                    sorted_values = sorted(values)
                    count = len(sorted_values)
                    snapshot_data[f"{name}_count"] = count
                    snapshot_data[f"{name}_sum"] = sum(sorted_values)
                    snapshot_data[f"{name}_avg"] = (
                        sum(sorted_values) / count
                    )
                    snapshot_data[f"{name}_p50"] = sorted_values[
                        int(count * 0.5)
                    ]
                    snapshot_data[f"{name}_p99"] = sorted_values[
                        min(int(count * 0.99), count - 1)
                    ]

            return snapshot_data

    def get_stats(self) -> Dict[str, Any]:
        """Return metrics statistics summary.

        Returns:
            A dictionary with summary of all collected metrics.
        """
        with self._lock:
            total_resolves = sum(
                sum(labels.values())
                for name, labels in self._counters.items()
                if name == METRIC_RESOLVE_TOTAL
            )
            total_load_balance = sum(
                sum(labels.values())
                for name, labels in self._counters.items()
                if name == METRIC_LOAD_BALANCE_TOTAL
            )
            total_canary = sum(
                sum(labels.values())
                for name, labels in self._counters.items()
                if name == METRIC_CANARY_ROUTE_TOTAL
            )
            return {
                "metrics": "ResolverMetrics",
                "total_resolves": total_resolves,
                "total_load_balance": total_load_balance,
                "total_canary_routes": total_canary,
                "counters": {
                    name: dict(labels)
                    for name, labels in self._counters.items()
                },
                "timers": {
                    name: {
                        "count": len(values),
                        "avg": (
                            sum(values) / len(values)
                            if values
                            else 0.0
                        ),
                    }
                    for name, values in self._timers.items()
                },
            }

    def _increment_counter(
        self, name: str, labels: Dict[str, str]
    ) -> None:
        with self._lock:
            if name not in self._counters:
                self._counters[name] = {}
            label_key = self._make_label_key(labels)
            self._counters[name][label_key] = (
                self._counters[name].get(label_key, 0) + 1
            )

    def _record_timer(self, name: str, value: float) -> None:
        with self._lock:
            if name not in self._timers:
                self._timers[name] = []
            self._timers[name].append(float(value))

    @staticmethod
    def _make_label_key(labels: Dict[str, str]) -> str:
        if not labels:
            return "{}"
        parts = [f"{k}={v}" for k, v in sorted(labels.items())]
        return "{" + ",".join(parts) + "}"

    def __repr__(self) -> str:
        with self._lock:
            total = sum(
                sum(labels.values())
                for labels in self._counters.values()
            )
            return f"ResolverMetrics(total_events={total})"