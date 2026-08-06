"""Runtime Metrics — Prometheus-compatible metrics collector for scheduler runtime."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class _Metric:
    """Base metric container."""

    def __init__(self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None) -> None:
        self.name = name
        self.description = description
        self.labels = labels or {}
        self._created_at = datetime.now(timezone.utc)


class _Counter(_Metric):
    """A monotonically increasing counter."""

    def __init__(self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None) -> None:
        super().__init__(name, description, labels)
        self._value: int = 0
        self._lock = threading.Lock()

    def inc(self, amount: int = 1) -> None:
        with self._lock:
            self._value += amount

    @property
    def value(self) -> int:
        return self._value


class _Gauge(_Metric):
    """A value that can go up and down."""

    def __init__(self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None) -> None:
        super().__init__(name, description, labels)
        self._value: float = 0.0
        self._lock = threading.Lock()

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value -= amount

    @property
    def value(self) -> float:
        return self._value


class _Histogram(_Metric):
    """Distribution of values."""

    def __init__(
        self, name: str, description: str = "",
        buckets: Optional[List[float]] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(name, description, labels)
        self._buckets = buckets or [0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0]
        self._bucket_counts: Dict[float, int] = {b: 0 for b in self._buckets}
        self._sum: float = 0.0
        self._count: int = 0
        self._lock = threading.Lock()

    def observe(self, value: float) -> None:
        with self._lock:
            for bound in self._buckets:
                if value <= bound:
                    self._bucket_counts[bound] += 1
            self._sum += value
            self._count += 1

    @property
    def sum(self) -> float:
        return self._sum

    @property
    def count(self) -> int:
        return self._count


class RuntimeMetricsCollector:
    """Collects runtime-level scheduler metrics.

    Metrics are Prometheus-compatible and can be exported via
    the metrics endpoint.

    Usage::

        collector = RuntimeMetricsCollector()
        collector.jobs_total.inc()
        collector.queue_size.set(42)
        collector.job_duration.observe(1.5)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

        # Counters
        self.jobs_total = _Counter(
            "icyquant_scheduler_jobs_total",
            "Total number of jobs processed",
        )
        self.triggers_total = _Counter(
            "icyquant_scheduler_trigger_total",
            "Total number of triggers evaluated",
        )
        self.dispatch_total = _Counter(
            "icyquant_scheduler_dispatch_total",
            "Total number of dispatches",
        )
        self.errors_total = _Counter(
            "icyquant_scheduler_errors_total",
            "Total number of scheduler errors",
        )
        self.snapshot_total = _Counter(
            "icyquant_scheduler_snapshot_total",
            "Total number of snapshots taken",
        )
        self.misfire_total = _Counter(
            "icyquant_scheduler_misfire_total",
            "Total number of misfired triggers",
        )

        # Gauges
        self.queue_size = _Gauge(
            "icyquant_scheduler_queue_size",
            "Current number of items in the scheduler queue",
        )
        self.active_jobs = _Gauge(
            "icyquant_scheduler_active_jobs",
            "Current number of active jobs",
        )
        self.active_workers = _Gauge(
            "icyquant_scheduler_active_workers",
            "Current number of active workers",
        )
        self.runtime_uptime = _Gauge(
            "icyquant_scheduler_runtime_uptime_seconds",
            "Scheduler runtime uptime in seconds",
        )

        # Histograms
        self.job_duration = _Histogram(
            "icyquant_scheduler_job_duration_seconds",
            "Job execution duration histogram",
        )
        self.trigger_evaluation = _Histogram(
            "icyquant_scheduler_trigger_evaluation_seconds",
            "Trigger evaluation time histogram",
        )
        self.dispatch_latency = _Histogram(
            "icyquant_scheduler_dispatch_latency_seconds",
            "Job dispatch latency histogram",
        )

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        with self._lock:
            for attr_name in dir(self):
                attr = getattr(self, attr_name, None)
                if isinstance(attr, _Counter):
                    attr._value = 0
                elif isinstance(attr, _Gauge):
                    attr._value = 0.0
                elif isinstance(attr, _Histogram):
                    attr._sum = 0.0
                    attr._count = 0
                    attr._bucket_counts = {b: 0 for b in attr._buckets}

    def snapshot(self) -> Dict[str, Any]:
        """Return a snapshot of all current metrics."""
        result: Dict[str, Any] = {}
        for attr_name in dir(self):
            if attr_name.startswith("_"):
                continue
            attr = getattr(self, attr_name, None)
            if isinstance(attr, _Counter):
                result[attr.name] = {"type": "counter", "value": attr.value}
            elif isinstance(attr, _Gauge):
                result[attr.name] = {"type": "gauge", "value": attr.value}
            elif isinstance(attr, _Histogram):
                result[attr.name] = {
                    "type": "histogram",
                    "sum": attr.sum,
                    "count": attr.count,
                    "buckets": dict(attr._bucket_counts),
                }
        return result

    def health_report(self) -> Dict[str, Any]:
        """Produce a health report for metrics."""
        return {"metrics_snapshot": self.snapshot()}
