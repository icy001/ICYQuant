"""Workflow Metrics — Prometheus-compatible metrics for workflow operations.

Metrics collected:
* icyquant_workflow_total — total registered workflows
* icyquant_workflow_execution_total — total executions (by status)
* icyquant_workflow_registration_total — total registrations
* icyquant_workflow_snapshot_total — total snapshots taken
* icyquant_workflow_runtime_total — active runtime instances
* icyquant_workflow_execution_duration_seconds — execution duration histogram
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class MetricCounter:
    """A monotonically increasing counter."""

    name: str
    help: str
    labels: Dict[str, str] = field(default_factory=dict)
    _value: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def inc(self, amount: int = 1) -> None:
        with self._lock:
            self._value += amount

    def value(self) -> int:
        with self._lock:
            return self._value


@dataclass
class MetricGauge:
    """A gauge that can go up and down."""

    name: str
    help: str
    labels: Dict[str, str] = field(default_factory=dict)
    _value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value -= amount

    def value(self) -> float:
        with self._lock:
            return self._value


@dataclass
class MetricHistogram:
    """A histogram that records observations into buckets."""

    name: str
    help: str
    buckets: List[float] = field(default_factory=lambda: [0.1, 0.5, 1, 5, 10, 30, 60, 300, 600, 1800, 3600])
    labels: Dict[str, str] = field(default_factory=dict)
    _count: int = 0
    _sum: float = 0.0
    _bucket_counts: Dict[float, int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def observe(self, value: float) -> None:
        with self._lock:
            self._count += 1
            self._sum += value
            for bucket in self.buckets:
                if value <= bucket:
                    self._bucket_counts[bucket] = self._bucket_counts.get(bucket, 0) + 1

    def count(self) -> int:
        with self._lock:
            return self._count

    def sum(self) -> float:
        with self._lock:
            return self._sum


class WorkflowMetrics:
    """Collector for workflow-related Prometheus-compatible metrics."""

    def __init__(self) -> None:
        # Counters
        self._workflow_total = MetricCounter(
            name="icyquant_workflow_total",
            help="Total number of registered workflows",
        )
        self._execution_total = MetricCounter(
            name="icyquant_workflow_execution_total",
            help="Total number of workflow executions",
        )
        self._registration_total = MetricCounter(
            name="icyquant_workflow_registration_total",
            help="Total number of workflow registrations",
        )
        self._snapshot_total = MetricCounter(
            name="icyquant_workflow_snapshot_total",
            help="Total number of snapshots taken",
        )

        # Gauges
        self._runtime_total = MetricGauge(
            name="icyquant_workflow_runtime_total",
            help="Number of active workflow runtime instances",
        )
        self._ready_queue_size = MetricGauge(
            name="icyquant_workflow_ready_queue_size",
            help="Current size of the ready queue",
        )

        # Histograms
        self._execution_duration = MetricHistogram(
            name="icyquant_workflow_execution_duration_seconds",
            help="Workflow execution duration in seconds",
        )
        self._node_execution_duration = MetricHistogram(
            name="icyquant_workflow_node_execution_duration_seconds",
            help="Node execution duration in seconds",
        )

        # Status-specific counters: execution_total by status
        self._status_counters: Dict[str, MetricCounter] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Counter operations
    # ------------------------------------------------------------------

    def increment_workflow_total(self) -> None:
        self._workflow_total.inc()

    def increment_execution_total(self, status: str = "started") -> None:
        self._execution_total.inc()
        with self._lock:
            if status not in self._status_counters:
                self._status_counters[status] = MetricCounter(
                    name=f"icyquant_workflow_execution_total",
                    help="Total executions by status",
                    labels={"status": status},
                )
            self._status_counters[status].inc()

    def increment_registration_total(self) -> None:
        self._registration_total.inc()

    def increment_snapshot_total(self) -> None:
        self._snapshot_total.inc()

    # ------------------------------------------------------------------
    # Gauge operations
    # ------------------------------------------------------------------

    def set_runtime_total(self, value: float) -> None:
        self._runtime_total.set(value)

    def increment_runtime_total(self) -> None:
        self._runtime_total.inc()

    def decrement_runtime_total(self) -> None:
        self._runtime_total.dec()

    def set_ready_queue_size(self, size: float) -> None:
        self._ready_queue_size.set(size)

    # ------------------------------------------------------------------
    # Histogram operations
    # ------------------------------------------------------------------

    def observe_execution_duration(self, seconds: float) -> None:
        self._execution_duration.observe(seconds)

    def observe_node_duration(self, seconds: float) -> None:
        self._node_execution_duration.observe(seconds)

    # ------------------------------------------------------------------
    # Snapshot / Export
    # ------------------------------------------------------------------

    def get_all_metrics(self) -> Dict[str, Any]:
        """Return all metrics as a dict suitable for JSON export."""
        return {
            "counters": {
                "icyquant_workflow_total": self._workflow_total.value(),
                "icyquant_workflow_execution_total": self._execution_total.value(),
                "icyquant_workflow_registration_total": self._registration_total.value(),
                "icyquant_workflow_snapshot_total": self._snapshot_total.value(),
            },
            "gauges": {
                "icyquant_workflow_runtime_total": self._runtime_total.value(),
                "icyquant_workflow_ready_queue_size": self._ready_queue_size.value(),
            },
            "histograms": {
                "icyquant_workflow_execution_duration_seconds": {
                    "count": self._execution_duration.count(),
                    "sum": self._execution_duration.sum(),
                },
                "icyquant_workflow_node_execution_duration_seconds": {
                    "count": self._node_execution_duration.count(),
                    "sum": self._node_execution_duration.sum(),
                },
            },
            "executions_by_status": {
                status: counter.value()
                for status, counter in self._status_counters.items()
            },
        }

    def reset(self) -> None:
        """Reset all metrics to zero (for testing)."""
        self._workflow_total = MetricCounter(name="icyquant_workflow_total", help="")
        self._execution_total = MetricCounter(name="icyquant_workflow_execution_total", help="")
        self._registration_total = MetricCounter(name="icyquant_workflow_registration_total", help="")
        self._snapshot_total = MetricCounter(name="icyquant_workflow_snapshot_total", help="")
        self._runtime_total = MetricGauge(name="icyquant_workflow_runtime_total", help="")
        self._ready_queue_size = MetricGauge(name="icyquant_workflow_ready_queue_size", help="")
        self._execution_duration = MetricHistogram(name="icyquant_workflow_execution_duration_seconds", help="")
        self._node_execution_duration = MetricHistogram(name="icyquant_workflow_node_execution_duration_seconds", help="")
        self._status_counters.clear()
