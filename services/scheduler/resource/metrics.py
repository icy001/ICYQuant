"""Resource Metrics — Prometheus-compatible metrics for resource scheduling.

Tracks CPU, memory, GPU usage, preemption events, auto-scaling actions,
and node scores across the cluster.
"""

from __future__ import annotations

import threading
from typing import Any, Dict


class _Counter:
    def __init__(self) -> None:
        self._v: int = 0
        self._l = threading.Lock()

    def inc(self, d: int = 1) -> None:
        with self._l:
            self._v += d

    def get(self) -> int:
        return self._v


class _Gauge:
    def __init__(self) -> None:
        self._v: float = 0.0
        self._l = threading.Lock()

    def set(self, v: float) -> None:
        with self._l:
            self._v = v

    def get(self) -> float:
        return self._v


class _Histogram:
    def __init__(self) -> None:
        self._s: float = 0.0
        self._c: int = 0
        self._mn: float = float("inf")
        self._mx: float = float("-inf")
        self._l = threading.Lock()

    def observe(self, v: float) -> None:
        with self._l:
            self._s += v
            self._c += 1
            if v < self._mn:
                self._mn = v
            if v > self._mx:
                self._mx = v

    def get_stats(self) -> Dict[str, float]:
        with self._l:
            return {
                "count": self._c, "sum": self._s,
                "avg": self._s / max(self._c, 1),
                "min": self._mn if self._c > 0 else 0.0,
                "max": self._mx if self._c > 0 else 0.0,
            }


class ResourceMetrics:
    """Metrics for resource scheduling.

    Usage::

        m = ResourceMetrics()
        m.cpu_usage.set(45.5)
        m.preemptions_total.inc()
    """

    def __init__(self) -> None:
        # Gauges
        self.cpu_usage_pct = _Gauge()
        self.memory_usage_pct = _Gauge()
        self.gpu_usage_pct = _Gauge()
        self.active_allocations = _Gauge()
        self.node_count = _Gauge()
        self.queue_depth = _Gauge()

        # Counters
        self.allocations_total = _Counter()
        self.releases_total = _Counter()
        self.preemptions_total = _Counter()
        self.scale_outs_total = _Counter()
        self.scale_ins_total = _Counter()
        self.allocation_failures = _Counter()
        self.quota_rejections = _Counter()

        # Histograms
        self.allocation_latency_ms = _Histogram()
        self.node_score = _Histogram()
        self.bin_packing_improvement_pct = _Histogram()

    def snapshot(self) -> Dict[str, Any]:
        return {
            "gauges": {
                "cpu_usage_pct": self.cpu_usage_pct.get(),
                "memory_usage_pct": self.memory_usage_pct.get(),
                "gpu_usage_pct": self.gpu_usage_pct.get(),
                "active_allocations": self.active_allocations.get(),
                "node_count": self.node_count.get(),
                "queue_depth": self.queue_depth.get(),
            },
            "counters": {
                "allocations_total": self.allocations_total.get(),
                "releases_total": self.releases_total.get(),
                "preemptions_total": self.preemptions_total.get(),
                "scale_outs_total": self.scale_outs_total.get(),
                "scale_ins_total": self.scale_ins_total.get(),
                "allocation_failures": self.allocation_failures.get(),
                "quota_rejections": self.quota_rejections.get(),
            },
            "histograms": {
                "allocation_latency_ms": self.allocation_latency_ms.get_stats(),
                "node_score": self.node_score.get_stats(),
                "bin_packing_improvement": self.bin_packing_improvement_pct.get_stats(),
            },
        }

    def health_report(self) -> Dict[str, Any]:
        return self.snapshot()
