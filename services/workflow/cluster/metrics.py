"""Cluster Metrics — Prometheus-compatible metrics for the distributed workflow cluster.

Metrics collected:

* icyquant_workflow_cluster_nodes — total nodes in cluster
* icyquant_workflow_leader_changes — leader election transitions
* icyquant_workflow_failover_total — total failover events
* icyquant_workflow_recovery_cluster_total — total recovery operations
* icyquant_workflow_shard_total — active shards
* icyquant_workflow_replication_latency — state/event replication latency
* icyquant_workflow_heartbeat_timeout — heartbeat timeout events
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ClusterMetricCounter:
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
class ClusterMetricGauge:
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
class ClusterMetricHistogram:
    """A histogram for latency tracking."""

    name: str
    help: str
    buckets: List[float] = field(default_factory=lambda: [0.001, 0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30, 60])
    _count: int = 0
    _sum: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def observe(self, value: float) -> None:
        with self._lock:
            self._count += 1
            self._sum += value

    def count(self) -> int:
        with self._lock:
            return self._count

    def sum(self) -> float:
        with self._lock:
            return self._sum


class ClusterMetrics:
    """Collector for cluster-related Prometheus-compatible metrics."""

    def __init__(self) -> None:
        # Counters
        self._cluster_nodes = ClusterMetricCounter(
            name="icyquant_workflow_cluster_nodes",
            help="Total number of nodes in the workflow cluster",
        )
        self._leader_changes = ClusterMetricCounter(
            name="icyquant_workflow_leader_changes",
            help="Total number of leader election transitions",
        )
        self._failover_total = ClusterMetricCounter(
            name="icyquant_workflow_failover_total",
            help="Total number of failover events triggered",
        )
        self._recovery_total = ClusterMetricCounter(
            name="icyquant_workflow_recovery_cluster_total",
            help="Total number of recovery operations performed",
        )
        self._shard_total = ClusterMetricCounter(
            name="icyquant_workflow_shard_total",
            help="Total number of active shards",
        )
        self._heartbeat_timeout = ClusterMetricCounter(
            name="icyquant_workflow_heartbeat_timeout",
            help="Total number of heartbeat timeout events",
        )

        # Gauges
        self._active_nodes = ClusterMetricGauge(
            name="icyquant_workflow_cluster_active_nodes",
            help="Number of currently active cluster nodes",
        )
        self._active_leases = ClusterMetricGauge(
            name="icyquant_workflow_cluster_active_leases",
            help="Number of currently active leases",
        )
        self._scheduler_queue = ClusterMetricGauge(
            name="icyquant_workflow_scheduler_queue_size",
            help="Current size of the scheduler queue",
        )

        # Histograms
        self._replication_latency = ClusterMetricHistogram(
            name="icyquant_workflow_replication_latency_seconds",
            help="State/event replication latency in seconds",
        )
        self._failover_duration = ClusterMetricHistogram(
            name="icyquant_workflow_failover_duration_seconds",
            help="Failover duration in seconds",
        )
        self._recovery_duration = ClusterMetricHistogram(
            name="icyquant_workflow_recovery_duration_seconds",
            help="Recovery operation duration in seconds",
        )

    # ------------------------------------------------------------------
    # Counter operations
    # ------------------------------------------------------------------

    def increment_nodes(self) -> None:
        self._cluster_nodes.inc()

    def increment_leader_changes(self) -> None:
        self._leader_changes.inc()

    def increment_failover_total(self) -> None:
        self._failover_total.inc()

    def increment_recovery_total(self) -> None:
        self._recovery_total.inc()

    def increment_shard_total(self) -> None:
        self._shard_total.inc()

    def increment_heartbeat_timeout(self) -> None:
        self._heartbeat_timeout.inc()

    # ------------------------------------------------------------------
    # Gauge operations
    # ------------------------------------------------------------------

    def set_active_nodes(self, count: float) -> None:
        self._active_nodes.set(count)

    def set_active_leases(self, count: float) -> None:
        self._active_leases.set(count)

    def set_scheduler_queue_size(self, size: float) -> None:
        self._scheduler_queue.set(size)

    # ------------------------------------------------------------------
    # Histogram operations
    # ------------------------------------------------------------------

    def observe_replication_latency(self, seconds: float) -> None:
        self._replication_latency.observe(seconds)

    def observe_failover_duration(self, seconds: float) -> None:
        self._failover_duration.observe(seconds)

    def observe_recovery_duration(self, seconds: float) -> None:
        self._recovery_duration.observe(seconds)

    # ------------------------------------------------------------------
    # Snapshot / Export
    # ------------------------------------------------------------------

    def get_all_metrics(self) -> Dict[str, Any]:
        return {
            "counters": {
                "icyquant_workflow_cluster_nodes": self._cluster_nodes.value(),
                "icyquant_workflow_leader_changes": self._leader_changes.value(),
                "icyquant_workflow_failover_total": self._failover_total.value(),
                "icyquant_workflow_recovery_cluster_total": self._recovery_total.value(),
                "icyquant_workflow_shard_total": self._shard_total.value(),
                "icyquant_workflow_heartbeat_timeout": self._heartbeat_timeout.value(),
            },
            "gauges": {
                "icyquant_workflow_cluster_active_nodes": self._active_nodes.value(),
                "icyquant_workflow_cluster_active_leases": self._active_leases.value(),
                "icyquant_workflow_scheduler_queue_size": self._scheduler_queue.value(),
            },
            "histograms": {
                "icyquant_workflow_replication_latency_seconds": {
                    "count": self._replication_latency.count(),
                    "sum": self._replication_latency.sum(),
                },
                "icyquant_workflow_failover_duration_seconds": {
                    "count": self._failover_duration.count(),
                    "sum": self._failover_duration.sum(),
                },
                "icyquant_workflow_recovery_duration_seconds": {
                    "count": self._recovery_duration.count(),
                    "sum": self._recovery_duration.sum(),
                },
            },
        }

    def reset(self) -> None:
        self._cluster_nodes = ClusterMetricCounter(name="icyquant_workflow_cluster_nodes", help="")
        self._leader_changes = ClusterMetricCounter(name="icyquant_workflow_leader_changes", help="")
        self._failover_total = ClusterMetricCounter(name="icyquant_workflow_failover_total", help="")
        self._recovery_total = ClusterMetricCounter(name="icyquant_workflow_recovery_cluster_total", help="")
        self._shard_total = ClusterMetricCounter(name="icyquant_workflow_shard_total", help="")
        self._heartbeat_timeout = ClusterMetricCounter(name="icyquant_workflow_heartbeat_timeout", help="")
        self._active_nodes = ClusterMetricGauge(name="icyquant_workflow_cluster_active_nodes", help="")
        self._active_leases = ClusterMetricGauge(name="icyquant_workflow_cluster_active_leases", help="")
        self._scheduler_queue = ClusterMetricGauge(name="icyquant_workflow_scheduler_queue_size", help="")
        self._replication_latency = ClusterMetricHistogram(name="icyquant_workflow_replication_latency_seconds", help="")
        self._failover_duration = ClusterMetricHistogram(name="icyquant_workflow_failover_duration_seconds", help="")
        self._recovery_duration = ClusterMetricHistogram(name="icyquant_workflow_recovery_duration_seconds", help="")
