"""
DAG Metrics — Prometheus-compatible metrics for DAG execution monitoring.

Metrics:
- icyquant_workflow_dag_total
- icyquant_workflow_parallel_total
- icyquant_workflow_retry_total
- icyquant_workflow_timeout_total
- icyquant_workflow_ready_queue_size
- icyquant_workflow_critical_path_seconds
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DAGMetricsSnapshot:
    """A point-in-time snapshot of DAG execution metrics."""

    dags_compiled: int = 0
    dags_executed: int = 0
    dags_completed: int = 0
    dags_failed: int = 0

    nodes_dispatched: int = 0
    nodes_completed: int = 0
    nodes_failed: int = 0
    nodes_retried: int = 0
    nodes_timed_out: int = 0

    parallel_executions: int = 0
    max_parallelism: int = 0
    ready_queue_size: int = 0

    critical_path_seconds: float = 0.0
    total_execution_seconds: float = 0.0


class DAGMetricsCollector:
    """
    Collects and exposes DAG execution metrics.

    In production, these would be registered with Prometheus.
    Currently uses in-memory counters with Prometheus-compatible naming.
    """

    def __init__(self):
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._snapshot = DAGMetricsSnapshot()

    def increment(self, metric: str, value: int = 1) -> None:
        """Increment a counter metric."""
        self._counters[metric] = self._counters.get(metric, 0) + value

    def set_gauge(self, metric: str, value: float) -> None:
        """Set a gauge metric."""
        self._gauges[metric] = value

    def observe(self, metric: str, value: float) -> None:
        """Record a histogram observation."""
        if metric not in self._histograms:
            self._histograms[metric] = []
        self._histograms[metric].append(value)

    # Convenience methods for specific metrics

    def record_dag_compiled(self) -> None:
        self.increment("icyquant_workflow_dag_total")
        self._snapshot.dags_compiled += 1

    def record_dag_executed(self) -> None:
        self._snapshot.dags_executed += 1

    def record_dag_completed(self) -> None:
        self._snapshot.dags_completed += 1

    def record_dag_failed(self) -> None:
        self._snapshot.dags_failed += 1

    def record_node_dispatched(self) -> None:
        self.increment("icyquant_workflow_parallel_total")
        self._snapshot.nodes_dispatched += 1
        self._snapshot.parallel_executions += 1

    def record_node_completed(self) -> None:
        self._snapshot.nodes_completed += 1

    def record_node_failed(self) -> None:
        self._snapshot.nodes_failed += 1

    def record_node_retried(self) -> None:
        self.increment("icyquant_workflow_retry_total")
        self._snapshot.nodes_retried += 1

    def record_node_timed_out(self) -> None:
        self.increment("icyquant_workflow_timeout_total")
        self._snapshot.nodes_timed_out += 1

    def record_ready_queue_size(self, size: int) -> None:
        self.set_gauge("icyquant_workflow_ready_queue_size", float(size))
        self._snapshot.ready_queue_size = size

    def record_critical_path(self, seconds: float) -> None:
        self.set_gauge("icyquant_workflow_critical_path_seconds", seconds)
        self._snapshot.critical_path_seconds = seconds

    def record_execution_time(self, seconds: float) -> None:
        self._snapshot.total_execution_seconds = seconds
        self.observe("icyquant_workflow_execution_duration_seconds", seconds)

    def get_snapshot(self) -> DAGMetricsSnapshot:
        """Get current metrics snapshot."""
        return self._snapshot

    def get_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []
        for name, value in self._counters.items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")
        for name, value in self._gauges.items():
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")
        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._snapshot = DAGMetricsSnapshot()
