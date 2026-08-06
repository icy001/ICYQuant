"""Observability metrics for ICYQuant Service Mesh.

Provides ``ObservabilityMetrics`` for tracking observability operations
including traces, spans, policy evaluations, SLO violations, anomalies,
runtime analyses, and dashboard requests.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ObservabilityMetrics:
    """Collects and reports observability metrics."""

    TRACE_TOTAL = "icyquant_mesh_trace_total"
    SPAN_TOTAL = "icyquant_mesh_span_total"
    POLICY_EVAL_TOTAL = "icyquant_mesh_policy_eval_total"
    SLO_VIOLATION_TOTAL = "icyquant_mesh_slo_violation_total"
    ANOMALY_TOTAL = "icyquant_mesh_anomaly_total"
    RUNTIME_ANALYSIS_TOTAL = "icyquant_mesh_runtime_analysis_total"
    DASHBOARD_REQUEST_TOTAL = "icyquant_mesh_dashboard_request_total"
    ACCESS_LOG_TOTAL = "icyquant_mesh_access_log_total"
    METRICS_FLUSH_TOTAL = "icyquant_mesh_metrics_flush_total"
    ACTIVE_TRACES = "icyquant_mesh_active_traces"
    ACTIVE_SPANS = "icyquant_mesh_active_spans"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._timers: Dict[str, List[float]] = {}
        self._start_time = time.monotonic()
        self._register_defaults()

    def _register_defaults(self) -> None:
        for metric in [
            self.TRACE_TOTAL,
            self.SPAN_TOTAL,
            self.POLICY_EVAL_TOTAL,
            self.SLO_VIOLATION_TOTAL,
            self.ANOMALY_TOTAL,
            self.RUNTIME_ANALYSIS_TOTAL,
            self.DASHBOARD_REQUEST_TOTAL,
            self.ACCESS_LOG_TOTAL,
            self.METRICS_FLUSH_TOTAL,
        ]:
            self._counters[metric] = 0
        self._gauges[self.ACTIVE_TRACES] = 0.0
        self._gauges[self.ACTIVE_SPANS] = 0.0

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

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        with self._lock:
            self._gauges[name] = value

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

    def increment_trace(self, labels: Optional[Dict[str, str]] = None) -> None:
        self.increment_counter(self.TRACE_TOTAL, labels=labels)

    def increment_span(self, labels: Optional[Dict[str, str]] = None) -> None:
        self.increment_counter(self.SPAN_TOTAL, labels=labels)

    def increment_policy_eval(self, labels: Optional[Dict[str, str]] = None) -> None:
        self.increment_counter(self.POLICY_EVAL_TOTAL, labels=labels)

    def increment_slo_violation(self, labels: Optional[Dict[str, str]] = None) -> None:
        self.increment_counter(self.SLO_VIOLATION_TOTAL, labels=labels)

    def increment_anomaly(self, labels: Optional[Dict[str, str]] = None) -> None:
        self.increment_counter(self.ANOMALY_TOTAL, labels=labels)

    def increment_runtime_analysis(self, labels: Optional[Dict[str, str]] = None) -> None:
        self.increment_counter(self.RUNTIME_ANALYSIS_TOTAL, labels=labels)

    def increment_dashboard_request(self, labels: Optional[Dict[str, str]] = None) -> None:
        self.increment_counter(self.DASHBOARD_REQUEST_TOTAL, labels=labels)

    def increment_access_log(self, labels: Optional[Dict[str, str]] = None) -> None:
        self.increment_counter(self.ACCESS_LOG_TOTAL, labels=labels)

    def increment_metrics_flush(self, labels: Optional[Dict[str, str]] = None) -> None:
        self.increment_counter(self.METRICS_FLUSH_TOTAL, labels=labels)

    def set_active_traces(self, count: int) -> None:
        self.set_gauge(self.ACTIVE_TRACES, float(count))

    def set_active_spans(self, count: int) -> None:
        self.set_gauge(self.ACTIVE_SPANS, float(count))

    def get_counter(self, name: str) -> int:
        with self._lock:
            return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float:
        with self._lock:
            return self._gauges.get(name, 0.0)

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            uptime = time.monotonic() - self._start_time
            timer_stats: Dict[str, Dict[str, float]] = {}
            for name, values in self._timers.items():
                if values:
                    timer_stats[name] = {
                        "count": len(values),
                        "min": min(values),
                        "max": max(values),
                        "avg": sum(values) / len(values),
                        "p50": _percentile(values, 50),
                        "p99": _percentile(values, 99),
                    }
            return {
                "uptime_s": uptime,
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "timer_stats": timer_stats,
            }

    def get_stats(self) -> Dict[str, Any]:
        return self.get_summary()

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._timers.clear()
            self._register_defaults()
            self._start_time = time.monotonic()


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)
