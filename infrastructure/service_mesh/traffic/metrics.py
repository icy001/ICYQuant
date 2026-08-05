"""Traffic metrics for ICYQuant Service Mesh.

Provides ``TrafficMetrics`` for tracking traffic management
counters including requests, retries, timeouts, circuit breaker
events, rate limiting, mirroring, canary, and blue-green.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TrafficMetrics:
    """Collects and reports traffic management metrics."""

    REQUESTS_TOTAL = "icyquant_mesh_requests_total"
    RETRY_TOTAL = "icyquant_mesh_retry_total"
    TIMEOUT_TOTAL = "icyquant_mesh_timeout_total"
    CIRCUIT_OPEN_TOTAL = "icyquant_mesh_circuit_open_total"
    RATE_LIMIT_TOTAL = "icyquant_mesh_rate_limit_total"
    MIRROR_TOTAL = "icyquant_mesh_mirror_total"
    CANARY_TOTAL = "icyquant_mesh_canary_total"
    BLUE_GREEN_TOTAL = "icyquant_mesh_blue_green_total"
    LATENCY_SECONDS = "icyquant_mesh_latency_seconds"
    CONNECTION_POOL_ACTIVE = "icyquant_mesh_conn_pool_active"
    OUTLIER_DETECTED = "icyquant_mesh_outlier_detected_total"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._timers: Dict[str, List[float]] = {}
        self._labels: Dict[str, Dict[str, str]] = {}
        self._start_time = time.monotonic()
        self._register_defaults()

    def _register_defaults(self) -> None:
        for metric in [
            self.REQUESTS_TOTAL,
            self.RETRY_TOTAL,
            self.TIMEOUT_TOTAL,
            self.CIRCUIT_OPEN_TOTAL,
            self.RATE_LIMIT_TOTAL,
            self.MIRROR_TOTAL,
            self.CANARY_TOTAL,
            self.BLUE_GREEN_TOTAL,
            self.OUTLIER_DETECTED,
        ]:
            self._counters[metric] = 0

    def increment_counter(
        self,
        name: str,
        value: int = 1,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        with self._lock:
            if name not in self._counters:
                self._counters[name] = 0
            self._counters[name] += value
            if labels:
                self._labels[name] = labels

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        with self._lock:
            self._gauges[name] = value
            if labels:
                self._labels[name] = labels

    def record_timer(
        self,
        name: str,
        duration_s: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        with self._lock:
            if name not in self._timers:
                self._timers[name] = []
            self._timers[name].append(duration_s)
            if len(self._timers[name]) > 1000:
                self._timers[name] = self._timers[name][-1000:]
            if labels:
                self._labels[name] = labels

    # Domain-specific increment methods
    def increment_requests(
        self, labels: Optional[Dict[str, str]] = None
    ) -> None:
        self.increment_counter(self.REQUESTS_TOTAL, labels=labels)

    def increment_retry(
        self, labels: Optional[Dict[str, str]] = None
    ) -> None:
        self.increment_counter(self.RETRY_TOTAL, labels=labels)

    def increment_timeout(
        self, labels: Optional[Dict[str, str]] = None
    ) -> None:
        self.increment_counter(self.TIMEOUT_TOTAL, labels=labels)

    def increment_circuit_open(
        self, labels: Optional[Dict[str, str]] = None
    ) -> None:
        self.increment_counter(self.CIRCUIT_OPEN_TOTAL, labels=labels)

    def increment_rate_limit(
        self, labels: Optional[Dict[str, str]] = None
    ) -> None:
        self.increment_counter(self.RATE_LIMIT_TOTAL, labels=labels)

    def increment_mirror(
        self, labels: Optional[Dict[str, str]] = None
    ) -> None:
        self.increment_counter(self.MIRROR_TOTAL, labels=labels)

    def increment_canary(
        self, labels: Optional[Dict[str, str]] = None
    ) -> None:
        self.increment_counter(self.CANARY_TOTAL, labels=labels)

    def increment_blue_green(
        self, labels: Optional[Dict[str, str]] = None
    ) -> None:
        self.increment_counter(self.BLUE_GREEN_TOTAL, labels=labels)

    def record_latency(
        self, duration_s: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        self.record_timer(self.LATENCY_SECONDS, duration_s, labels=labels)

    def set_pool_active(
        self, value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        self.set_gauge(self.CONNECTION_POOL_ACTIVE, value, labels=labels)

    def increment_outlier(
        self, labels: Optional[Dict[str, str]] = None
    ) -> None:
        self.increment_counter(self.OUTLIER_DETECTED, labels=labels)

    def get_counter(self, name: str) -> int:
        with self._lock:
            return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float:
        with self._lock:
            return self._gauges.get(name, 0.0)

    def get_timers(self, name: str) -> List[float]:
        with self._lock:
            return list(self._timers.get(name, []))

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            uptime = time.monotonic() - self._start_time
            timer_stats: Dict[str, Dict[str, float]] = {}
            for name, durations in self._timers.items():
                if durations:
                    sorted_d = sorted(durations)
                    count = len(sorted_d)
                    idx_p50 = int(count * 0.50) if count > 0 else 0
                    idx_p95 = int(count * 0.95) if count > 0 else 0
                    idx_p99 = int(count * 0.99) if count > 0 else 0
                    timer_stats[name] = {
                        "count": count,
                        "avg": sum(sorted_d) / count,
                        "min": sorted_d[0],
                        "max": sorted_d[-1],
                        "p50": sorted_d[min(idx_p50, count - 1)],
                        "p95": sorted_d[min(idx_p95, count - 1)],
                        "p99": sorted_d[min(idx_p99, count - 1)],
                    }
            return {
                "uptime_s": uptime,
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "timer_stats": timer_stats,
                "labels": dict(self._labels),
            }

    def get_stats(self) -> Dict[str, Any]:
        return self.get_summary()

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._timers.clear()
            self._labels.clear()
            self._register_defaults()
            self._start_time = time.monotonic()