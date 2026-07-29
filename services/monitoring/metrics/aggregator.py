"""Metrics Aggregator.

Computes aggregate statistics over time windows:
- 1m, 5m, 15m, 1h, 1d rolling windows
- Min, Max, Avg, P50, P95, P99 percentiles
- Rate computation (delta/time)

Usage::

    agg = MetricsAggregator()
    agg.record("order_latency", 12.5)
    agg.record("order_latency", 8.3)
    stats = agg.get_stats("order_latency", AggregationWindow.M1)
    print(stats["avg"])
"""

from __future__ import annotations

import bisect
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class AggregationWindow(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    ALL = "all"


WINDOW_SECONDS: Dict[AggregationWindow, float] = {
    AggregationWindow.M1: 60.0,
    AggregationWindow.M5: 300.0,
    AggregationWindow.M15: 900.0,
    AggregationWindow.H1: 3600.0,
    AggregationWindow.H4: 14400.0,
    AggregationWindow.D1: 86400.0,
    AggregationWindow.ALL: float("inf"),
}


@dataclass
class AggregatedStats:
    """Aggregate statistics for a metric."""

    metric_name: str
    window: AggregationWindow
    count: int = 0
    min: float = 0.0
    max: float = 0.0
    avg: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    stddev: float = 0.0
    total: float = 0.0
    latest: float = 0.0
    rate: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric_name,
            "window": self.window.value,
            "count": self.count,
            "min": round(self.min, 4),
            "max": round(self.max, 4),
            "avg": round(self.avg, 4),
            "p50": round(self.p50, 4),
            "p95": round(self.p95, 4),
            "p99": round(self.p99, 4),
            "stddev": round(self.stddev, 4),
            "total": round(self.total, 4),
            "latest": round(self.latest, 4),
            "rate": round(self.rate, 4),
            "timestamp": self.timestamp,
        }


class MetricsAggregator:
    """Rolling-window metrics aggregator.

    Stores timestamped values for each metric name and computes
    statistics for configurable time windows.
    """

    def __init__(self, max_points_per_metric: int = 10000) -> None:
        self._data: Dict[str, List[Tuple[float, float]]] = {}
        self._max_points = max_points_per_metric

    def record(self, metric_name: str, value: float) -> None:
        """Record a metric value at the current time."""
        if metric_name not in self._data:
            self._data[metric_name] = []
        self._data[metric_name].append((time.time(), value))
        # Trim old data
        if len(self._data[metric_name]) > self._max_points:
            self._data[metric_name] = self._data[metric_name][-self._max_points:]

    def get_stats(
        self, metric_name: str, window: AggregationWindow = AggregationWindow.M5
    ) -> AggregatedStats:
        """Compute aggregate statistics for a metric over a window."""
        data = self._data.get(metric_name, [])
        if not data:
            return AggregatedStats(
                metric_name=metric_name,
                window=window,
            )

        cutoff = time.time() - WINDOW_SECONDS[window]
        # Find start index via binary search
        timestamps = [t for t, _ in data]
        idx = bisect.bisect_left(timestamps, cutoff)
        window_data = data[idx:]

        if not window_data:
            return AggregatedStats(
                metric_name=metric_name,
                window=window,
            )

        values = sorted(v for _, v in window_data)
        n = len(values)

        avg = sum(values) / n
        stddev = (
            (sum((v - avg) ** 2 for v in values) / n) ** 0.5 if n > 1 else 0.0
        )

        # Compute rate (events per second)
        time_span = timestamps[-1] - timestamps[0] if len(timestamps) > 1 else 1.0
        rate = n / max(time_span, 1.0)

        return AggregatedStats(
            metric_name=metric_name,
            window=window,
            count=n,
            min=values[0],
            max=values[-1],
            avg=avg,
            p50=self._percentile(values, 50),
            p95=self._percentile(values, 95),
            p99=self._percentile(values, 99),
            stddev=stddev,
            total=sum(values),
            latest=window_data[-1][1],
            rate=rate,
        )

    def get_all_stats(self, metric_name: str) -> Dict[str, AggregatedStats]:
        """Get stats for all time windows."""
        return {
            w.value: self.get_stats(metric_name, w)
            for w in AggregationWindow
        }

    def list_metrics(self) -> List[str]:
        """List all tracked metric names."""
        return list(self._data.keys())

    def clear(self) -> None:
        """Clear all stored data."""
        self._data.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _percentile(sorted_values: List[float], pct: float) -> float:
        """Compute percentile from sorted values using linear interpolation."""
        if not sorted_values:
            return 0.0
        n = len(sorted_values)
        if n == 1:
            return sorted_values[0]
        k = (pct / 100.0) * (n - 1)
        f = int(k)
        c = k - f
        if f + 1 >= n:
            return sorted_values[-1]
        return sorted_values[f] + c * (sorted_values[f + 1] - sorted_values[f])
