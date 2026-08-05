"""Service discovery metrics tracking.

Provides ``ServiceDiscoveryMetrics`` for thread-safe collection of
service discovery counters, gauges, and histograms covering
registration, deregistration, discovery, lease, cache, and namespace
operations.

Metrics:
- icyquant_service_registered_total
- icyquant_service_deregistered_total
- icyquant_service_discovery_total
- icyquant_service_registry_latency_seconds
- icyquant_service_lease_renewal_total
- icyquant_service_lease_expiry_total
- icyquant_service_namespace_total
- icyquant_service_cache_hit_total
- icyquant_service_cache_miss_total
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ServiceDiscoveryMetrics:
    """Tracks metrics for the service discovery subsystem.

    Provides counters, gauges, and histograms for monitoring
    registration, discovery, lease, cache, and namespace operations.
    Thread-safe via a reentrant lock.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._gauges: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._histograms: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
            dict
        )
        self._observations: Dict[str, List[float]] = defaultdict(list)

    def record_registration(
        self, service_name: str, success: bool, duration: float
    ) -> None:
        """Record a service registration attempt."""
        with self._lock:
            self._increment_counter(
                "icyquant_service_registered_total", service_name
            )
            if success:
                self._increment_counter(
                    "icyquant_service_registered_success_total", service_name
                )
            else:
                self._increment_counter(
                    "icyquant_service_registered_failure_total", service_name
                )
            self._record_histogram(
                "icyquant_service_registry_latency_seconds",
                service_name,
                float(duration),
            )
            logger.debug(
                "Registration recorded for '%s' (success=%s, %.4fs).",
                service_name,
                success,
                duration,
            )

    def record_deregistration(
        self, service_name: str, success: bool
    ) -> None:
        """Record a service deregistration attempt."""
        with self._lock:
            self._increment_counter(
                "icyquant_service_deregistered_total", service_name
            )
            if success:
                self._increment_counter(
                    "icyquant_service_deregistered_success_total", service_name
                )
            else:
                self._increment_counter(
                    "icyquant_service_deregistered_failure_total", service_name
                )

    def record_discovery(
        self, service_name: str, duration: float, result_count: int
    ) -> None:
        """Record a service discovery operation."""
        with self._lock:
            self._increment_counter(
                "icyquant_service_discovery_total", service_name
            )
            self._record_histogram(
                "icyquant_service_registry_latency_seconds",
                service_name,
                float(duration),
            )
            self._set_gauge(
                "icyquant_service_discovery_result_count",
                service_name,
                float(result_count),
            )

    def record_lease_renewal(self, service_name: str, success: bool) -> None:
        """Record a lease renewal attempt."""
        with self._lock:
            self._increment_counter(
                "icyquant_service_lease_renewal_total", service_name
            )
            if not success:
                self._increment_counter(
                    "icyquant_service_lease_renewal_failure_total", service_name
                )

    def record_lease_expiry(self, service_name: str) -> None:
        """Record a lease expiry."""
        with self._lock:
            self._increment_counter(
                "icyquant_service_lease_expiry_total", service_name
            )

    def record_namespace_operation(self, operation: str) -> None:
        """Record a namespace-level operation."""
        with self._lock:
            self._increment_counter(
                "icyquant_service_namespace_total", operation or "unknown"
            )

    def record_cache_hit(self, service_name: str) -> None:
        """Record a service discovery cache hit."""
        with self._lock:
            self._increment_counter(
                "icyquant_service_cache_hit_total", service_name
            )

    def record_cache_miss(self, service_name: str) -> None:
        """Record a service discovery cache miss."""
        with self._lock:
            self._increment_counter(
                "icyquant_service_cache_miss_total", service_name
            )

    def snapshot(self) -> Dict[str, Any]:
        """Return a point-in-time snapshot of all metrics."""
        with self._lock:
            return {
                "counters": {
                    name: dict(entries)
                    for name, entries in self._counters.items()
                },
                "gauges": {
                    name: dict(entries)
                    for name, entries in self._gauges.items()
                },
                "histograms": {
                    name: {
                        key: dict(values)
                        for key, values in hist_data.items()
                    }
                    for name, hist_data in self._histograms.items()
                },
            }

    def get_counter(self, name: str) -> int:
        """Return the sum of a named counter across all labels."""
        with self._lock:
            entries = self._counters.get(name, {})
            return int(sum(entries.values()))

    def get_gauge(self, name: str) -> float:
        """Return the sum of a named gauge across all labels."""
        with self._lock:
            entries = self._gauges.get(name, {})
            return float(sum(entries.values()))

    def get_histogram(self, name: str) -> Dict[str, float]:
        """Return summary statistics for a named histogram."""
        with self._lock:
            all_values: List[float] = list(self._observations.get(name, []))
        if not all_values:
            return {"avg": 0.0, "min": 0.0, "max": 0.0, "count": 0}
        return {
            "avg": sum(all_values) / len(all_values),
            "min": min(all_values),
            "max": max(all_values),
            "count": len(all_values),
        }

    def reset(self) -> None:
        """Reset all metrics to zero."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._observations.clear()
            logger.info("Service discovery metrics reset.")

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics of the metrics system itself."""
        with self._lock:
            return {
                "counter_count": len(self._counters),
                "gauge_count": len(self._gauges),
                "histogram_count": len(self._histograms),
                "counters": {
                    name: int(sum(entries.values()))
                    for name, entries in self._counters.items()
                },
                "gauges": {
                    name: float(sum(entries.values()))
                    for name, entries in self._gauges.items()
                },
                "histograms": {
                    name: self.get_histogram(name)
                    for name in self._histograms
                },
            }

    # ── Internal helpers ──

    @staticmethod
    def _make_key(label: str) -> str:
        return label or "__total__"

    def _increment_counter(
        self, name: str, label: str, value: float = 1.0
    ) -> None:
        key = self._make_key(label)
        self._counters[name][key] = self._counters[name].get(key, 0.0) + value

    def _set_gauge(self, name: str, label: str, value: float) -> None:
        key = self._make_key(label)
        self._gauges[name][key] = value

    def _record_histogram(
        self, name: str, label: str, value: float
    ) -> None:
        key = self._make_key(label)
        entry = self._histograms[name].get(key)
        if entry is None:
            entry = {
                "count": 0,
                "sum": 0.0,
                "min": float("inf"),
                "max": float("-inf"),
            }
            self._histograms[name][key] = entry
        entry["count"] += 1
        entry["sum"] += value
        entry["min"] = min(entry["min"], value)
        entry["max"] = max(entry["max"], value)
        entry["value"] = value
        self._observations[name].append(value)
