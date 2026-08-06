"""Runtime Metrics — telemetry and resource monitoring for research runtimes.

Provides resource usage tracking, performance metrics, and telemetry
export for research execution environments.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of runtime metrics."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class ResourceUsage:
    """Snapshot of resource utilization at a point in time."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    disk_read_bytes: int = 0
    disk_write_bytes: int = 0
    network_rx_bytes: int = 0
    network_tx_bytes: int = 0
    gpu_utilization: Optional[float] = None
    gpu_memory_mb: Optional[float] = None
    open_files: int = 0
    thread_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_percent": self.cpu_percent,
            "memory_mb": self.memory_mb,
            "memory_percent": self.memory_percent,
            "disk_read_bytes": self.disk_read_bytes,
            "disk_write_bytes": self.disk_write_bytes,
            "network_rx_bytes": self.network_rx_bytes,
            "network_tx_bytes": self.network_tx_bytes,
            "gpu_utilization": self.gpu_utilization,
            "gpu_memory_mb": self.gpu_memory_mb,
            "open_files": self.open_files,
            "thread_count": self.thread_count,
        }


class RuntimeMetrics:
    """Collects and exposes runtime-level metrics for research executions.

    Tracks resource usage over time and provides aggregated statistics
    for monitoring and optimization.

    Usage::

        metrics = RuntimeMetrics()
        metrics.record_usage(ResourceUsage(cpu_percent=45.2, memory_mb=128.0))
        summary = metrics.summary()
    """

    # Global counters
    _total_executions: int = 0
    _total_errors: int = 0
    _total_cpu_seconds: float = 0.0
    _total_memory_mb_seconds: float = 0.0
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        self._env_metrics: Dict[str, List[ResourceUsage]] = {}
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}

    # ---- Resource Tracking ----

    def record_usage(self, env_id: str, usage: ResourceUsage) -> None:
        """Record a resource usage sample for an environment."""
        self._env_metrics.setdefault(env_id, []).append(usage)

    def get_usage(self, env_id: str) -> List[ResourceUsage]:
        """Get all resource usage samples for an environment."""
        return self._env_metrics.get(env_id, [])

    def latest_usage(self, env_id: str) -> Optional[ResourceUsage]:
        samples = self._env_metrics.get(env_id, [])
        return samples[-1] if samples else None

    # ---- Counters ----

    def increment(self, name: str, delta: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + delta

    def counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    # ---- Gauges ----

    def set_gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def gauge(self, name: str) -> float:
        return self._gauges.get(name, 0.0)

    # ---- Histograms ----

    def observe(self, name: str, value: float) -> None:
        self._histograms.setdefault(name, []).append(value)

    def histogram_stats(self, name: str) -> Dict[str, float]:
        values = self._histograms.get(name, [])
        if not values:
            return {"count": 0, "min": 0, "max": 0, "mean": 0, "p50": 0, "p95": 0, "p99": 0}
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        return {
            "count": n,
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "mean": sum(sorted_vals) / n,
            "p50": sorted_vals[int(n * 0.50)],
            "p95": sorted_vals[int(n * 0.95)],
            "p99": sorted_vals[int(n * 0.99)],
        }

    # ---- Aggregation ----

    def aggregate_usage(self, env_id: str) -> Dict[str, Any]:
        """Compute aggregate resource usage for an environment."""
        samples = self._env_metrics.get(env_id, [])
        if not samples:
            return {"env_id": env_id, "samples": 0}
        cpu_values = [s.cpu_percent for s in samples]
        mem_values = [s.memory_mb for s in samples]
        return {
            "env_id": env_id,
            "samples": len(samples),
            "duration_seconds": (samples[-1].timestamp - samples[0].timestamp).total_seconds(),
            "cpu_avg": sum(cpu_values) / len(cpu_values),
            "cpu_max": max(cpu_values),
            "cpu_min": min(cpu_values),
            "memory_avg_mb": sum(mem_values) / len(mem_values),
            "memory_max_mb": max(mem_values),
            "memory_min_mb": min(mem_values),
        }

    def summary(self) -> Dict[str, Any]:
        """Overall metrics summary across all environments."""
        active_envs = len([e for e in self._env_metrics.values() if e])
        return {
            "active_environments": active_envs,
            "total_executions": RuntimeMetrics._total_executions,
            "total_errors": RuntimeMetrics._total_errors,
            "cpu_seconds": RuntimeMetrics._total_cpu_seconds,
            "memory_mb_seconds": RuntimeMetrics._total_memory_mb_seconds,
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._env_metrics.clear()
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()

    def __repr__(self) -> str:
        return (
            f"RuntimeMetrics(envs={len(self._env_metrics)}, "
            f"counters={len(self._counters)}, gauges={len(self._gauges)})"
        )
