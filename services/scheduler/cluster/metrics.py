"""Cluster Metrics — Prometheus-compatible metrics for the scheduler cluster.

Exports metrics for:
* Node count and state changes
* Leader election events
* Failover occurrences
* Queue replication latency
* Queue depth per type
* Distributed lock operations
* Cluster recovery events
"""

from __future__ import annotations

import threading
from typing import Any, Dict


class _Counter:
    """Simple thread-safe counter."""

    def __init__(self) -> None:
        self._value: int = 0
        self._lock = threading.Lock()

    def inc(self, delta: int = 1) -> None:
        with self._lock:
            self._value += delta

    def get(self) -> int:
        return self._value


class _Gauge:
    """Simple thread-safe gauge."""

    def __init__(self, initial: float = 0.0) -> None:
        self._value: float = initial
        self._lock = threading.Lock()

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    def inc(self, delta: float = 1.0) -> None:
        with self._lock:
            self._value += delta

    def dec(self, delta: float = 1.0) -> None:
        with self._lock:
            self._value -= delta

    def get(self) -> float:
        return self._value


class _Histogram:
    """Simple histogram with pre-defined buckets."""

    def __init__(self, buckets: tuple = (0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30, 60)) -> None:
        self._buckets = buckets
        self._count: int = 0
        self._sum: float = 0.0
        self._lock = threading.Lock()

    def observe(self, value: float) -> None:
        with self._lock:
            self._count += 1
            self._sum += value

    def get(self) -> Dict[str, Any]:
        return {"count": self._count, "sum": self._sum}


class ClusterMetrics:
    """Cluster-wide Prometheus-compatible metrics.

    Usage::

        metrics = ClusterMetrics()
        metrics.cluster_nodes.set(3)
        metrics.leader_changes.inc()
        metrics.failover_total.inc()
    """

    def __init__(self) -> None:
        # Counters
        self.leader_changes = _Counter()
        self.failover_total = _Counter()
        self.distributed_lock_total = _Counter()
        self.cluster_recovery_total = _Counter()
        self.queue_enqueue_total = _Counter()
        self.queue_dequeue_total = _Counter()
        self.queue_dlq_total = _Counter()

        # Gauges
        self.cluster_nodes = _Gauge()
        self.queue_depth = _Gauge()
        self.queue_ready_depth = _Gauge()
        self.queue_delayed_depth = _Gauge()
        self.queue_retry_depth = _Gauge()
        self.queue_dlq_depth = _Gauge()

        # Histograms
        self.queue_replication_latency = _Histogram()
        self.failover_duration = _Histogram(buckets=(0.1, 0.5, 1, 5, 10, 30, 60))
        self.recovery_duration = _Histogram(buckets=(0.5, 1, 5, 10, 30, 60, 120))

    def snapshot(self) -> Dict[str, Any]:
        """Return a snapshot of all metric values."""
        return {
            # Counters
            "icyquant_scheduler_leader_changes": self.leader_changes.get(),
            "icyquant_scheduler_failover_total": self.failover_total.get(),
            "icyquant_scheduler_distributed_lock_total": self.distributed_lock_total.get(),
            "icyquant_scheduler_cluster_recovery_total": self.cluster_recovery_total.get(),
            "icyquant_scheduler_queue_enqueue_total": self.queue_enqueue_total.get(),
            "icyquant_scheduler_queue_dequeue_total": self.queue_dequeue_total.get(),
            "icyquant_scheduler_queue_dlq_total": self.queue_dlq_total.get(),
            # Gauges
            "icyquant_scheduler_cluster_nodes": self.cluster_nodes.get(),
            "icyquant_scheduler_queue_depth": self.queue_depth.get(),
            "icyquant_scheduler_queue_ready_depth": self.queue_ready_depth.get(),
            "icyquant_scheduler_queue_delayed_depth": self.queue_delayed_depth.get(),
            "icyquant_scheduler_queue_retry_depth": self.queue_retry_depth.get(),
            "icyquant_scheduler_queue_dlq_depth": self.queue_dlq_depth.get(),
            # Histograms
            "icyquant_scheduler_queue_replication_latency": self.queue_replication_latency.get(),
            "icyquant_scheduler_failover_duration": self.failover_duration.get(),
            "icyquant_scheduler_recovery_duration": self.recovery_duration.get(),
        }
