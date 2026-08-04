"""
Runtime metrics collection.

Collects and exposes Prometheus-compatible metrics
for the dynamic configuration platform.

Metrics:
- icyquant_config_reload_total
- icyquant_config_reload_success_total
- icyquant_config_reload_failure_total
- icyquant_config_snapshot_version
- icyquant_config_subscriber_total
- icyquant_config_reload_duration_seconds
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional


class MetricsCollector:
    """
    Thread-safe metrics collector.

    Collects counters, gauges, and histograms for
    the dynamic configuration platform.

    Supports:
    - Counter metrics (monotonically increasing)
    - Gauge metrics (current value)
    - Histogram metrics (distribution of values)
    - Label-based filtering
    - Prometheus-compatible output
    """

    def __init__(
        self,
    ) -> None:
        """Initialize metrics collector."""
        self._counters: Dict[str, CounterMetric] = {}
        self._gauges: Dict[str, GaugeMetric] = {}
        self._histograms: Dict[str, HistogramMetric] = {}
        self._lock = threading.Lock()

    # ── Counter Metrics ──

    def create_counter(
        self,
        name: str,
        description: str = "",
        labels: Optional[List[str]] = None,
    ) -> CounterMetric:
        """
        Create a counter metric.

        Args:
            name: Metric name (e.g., 'reload_total').
            description: Metric description.
            labels: Label names for dimensional metrics.

        Returns:
            Counter metric instance.
        """
        with self._lock:
            if name not in self._counters:
                self._counters[name] = CounterMetric(
                    name=name,
                    description=description,
                    label_names=labels or [],
                )
            return self._counters[name]

    def inc_counter(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Increment a counter metric.

        Args:
            name: Metric name.
            value: Increment value.
            labels: Label values.
        """
        with self._lock:
            if name in self._counters:
                self._counters[name].inc(value, labels)

    # ── Gauge Metrics ──

    def create_gauge(
        self,
        name: str,
        description: str = "",
        labels: Optional[List[str]] = None,
    ) -> GaugeMetric:
        """
        Create a gauge metric.

        Args:
            name: Metric name.
            description: Metric description.
            labels: Label names.

        Returns:
            Gauge metric instance.
        """
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = GaugeMetric(
                    name=name,
                    description=description,
                    label_names=labels or [],
                )
            return self._gauges[name]

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Set a gauge metric value."""
        with self._lock:
            if name in self._gauges:
                self._gauges[name].set(value, labels)

    def inc_gauge(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Increment a gauge metric."""
        with self._lock:
            if name in self._gauges:
                self._gauges[name].inc(value, labels)

    def dec_gauge(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Decrement a gauge metric."""
        with self._lock:
            if name in self._gauges:
                self._gauges[name].dec(value, labels)

    # ── Histogram Metrics ──

    def create_histogram(
        self,
        name: str,
        description: str = "",
        buckets: Optional[List[float]] = None,
        labels: Optional[List[str]] = None,
    ) -> HistogramMetric:
        """
        Create a histogram metric.

        Args:
            name: Metric name.
            description: Metric description.
            buckets: Histogram bucket boundaries.
            labels: Label names.

        Returns:
            Histogram metric instance.
        """
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = HistogramMetric(
                    name=name,
                    description=description,
                    buckets=buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
                    label_names=labels or [],
                )
            return self._histograms[name]

    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a histogram observation."""
        with self._lock:
            if name in self._histograms:
                self._histograms[name].observe(value, labels)

    # ── Metrics Export ──

    def get_all_metrics(
        self,
    ) -> Dict[str, Any]:
        """Get all collected metrics."""
        with self._lock:
            return {
                "counters": {
                    name: metric.get_values()
                    for name, metric in self._counters.items()
                },
                "gauges": {
                    name: metric.get_values()
                    for name, metric in self._gauges.items()
                },
                "histograms": {
                    name: metric.get_values()
                    for name, metric in self._histograms.items()
                },
            }

    def get_prometheus_format(
        self,
    ) -> str:
        """Export metrics in Prometheus text format."""
        lines: List[str] = []

        for metric in self._counters.values():
            lines.extend(metric.to_prometheus())

        for metric in self._gauges.values():
            lines.extend(metric.to_prometheus())

        for metric in self._histograms.values():
            lines.extend(metric.to_prometheus())

        return "\n".join(lines) + "\n"


class CounterMetric:
    """Counter metric (monotonically increasing)."""

    def __init__(
        self,
        name: str,
        description: str,
        label_names: List[str],
    ) -> None:
        self.name = name
        self.description = description
        self.label_names = label_names
        self._values: Dict[str, float] = {}

    def inc(
        self,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Increment counter."""
        key = self._make_key(labels)
        self._values[key] = self._values.get(key, 0) + value

    def get_values(
        self,
    ) -> Dict[str, float]:
        """Get all counter values."""
        return dict(self._values)

    def _make_key(
        self,
        labels: Optional[Dict[str, str]],
    ) -> str:
        if not labels:
            return "__total__"
        parts = [f"{k}={v}" for k, v in sorted(labels.items())]
        return ",".join(parts)

    def to_prometheus(
        self,
    ) -> List[str]:
        """Export in Prometheus format."""
        lines = [f"# HELP {self.name} {self.description}"]
        lines.append(f"# TYPE {self.name} counter")
        for key, value in self._values.items():
            label_str = self._format_labels(key)
            lines.append(f"{self.name}{label_str} {value}")
        return lines

    def _format_labels(
        self,
        key: str,
    ) -> str:
        if key == "__total__":
            return ""
        return "{" + key + "}"


class GaugeMetric:
    """Gauge metric (can go up and down)."""

    def __init__(
        self,
        name: str,
        description: str,
        label_names: List[str],
    ) -> None:
        self.name = name
        self.description = description
        self.label_names = label_names
        self._values: Dict[str, float] = {}

    def set(
        self,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Set gauge value."""
        key = self._make_key(labels)
        self._values[key] = value

    def inc(
        self,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Increment gauge."""
        key = self._make_key(labels)
        self._values[key] = self._values.get(key, 0) + value

    def dec(
        self,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Decrement gauge."""
        key = self._make_key(labels)
        self._values[key] = self._values.get(key, 0) - value

    def get_values(
        self,
    ) -> Dict[str, float]:
        return dict(self._values)

    def _make_key(
        self,
        labels: Optional[Dict[str, str]],
    ) -> str:
        if not labels:
            return "__total__"
        parts = [f"{k}={v}" for k, v in sorted(labels.items())]
        return ",".join(parts)

    def to_prometheus(
        self,
    ) -> List[str]:
        lines = [f"# HELP {self.name} {self.description}"]
        lines.append(f"# TYPE {self.name} gauge")
        for key, value in self._values.items():
            label_str = self._format_labels(key)
            lines.append(f"{self.name}{label_str} {value}")
        return lines

    def _format_labels(
        self,
        key: str,
    ) -> str:
        if key == "__total__":
            return ""
        return "{" + key + "}"


class HistogramMetric:
    """Histogram metric (value distribution)."""

    def __init__(
        self,
        name: str,
        description: str,
        buckets: List[float],
        label_names: List[str],
    ) -> None:
        self.name = name
        self.description = description
        self.buckets = sorted(buckets)
        self.label_names = label_names
        self._counts: Dict[str, float] = {}
        self._sums: Dict[str, float] = {}

    def observe(
        self,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a value observation."""
        key = self._make_key(labels)
        for bucket in self.buckets:
            if key not in self._counts:
                self._counts[key] = 0
                self._sums[key] = 0.0
            if value <= bucket:
                self._counts[f"{key}__le_{bucket}"] = (
                    self._counts.get(f"{key}__le_{bucket}", 0) + 1
                )
        self._counts[key] = self._counts.get(key, 0) + 1
        self._sums[key] = self._sums.get(key, 0) + value

    def get_values(
        self,
    ) -> Dict[str, Any]:
        """Get histogram values."""
        return {
            "counts": dict(self._counts),
            "sums": dict(self._sums),
        }

    def _make_key(
        self,
        labels: Optional[Dict[str, str]],
    ) -> str:
        if not labels:
            return "__total__"
        parts = [f"{k}={v}" for k, v in sorted(labels.items())]
        return ",".join(parts)

    def to_prometheus(
        self,
    ) -> List[str]:
        """Export in Prometheus format."""
        lines = [f"# HELP {self.name} {self.description}"]
        lines.append(f"# TYPE {self.name} histogram")

        for key in set(k.split("__le_")[0] for k in self._counts.keys()):
            for bucket in self.buckets:
                count = self._counts.get(f"{key}__le_{bucket}", 0)
                label_str = self._format_labels(key, bucket)
                lines.append(f"{self.name}_bucket{label_str} {count}")

            count = self._counts.get(key, 0)
            label_str = self._format_labels(key, "+Inf")
            lines.append(f"{self.name}_bucket{label_str} {count}")

            sum_val = self._sums.get(key, 0)
            sum_label = self._format_labels(key, None)
            lines.append(f"{self.name}_sum{sum_label} {sum_val}")
            lines.append(f"{self.name}_count{sum_label} {count}")

        return lines

    def _format_labels(
        self,
        key: str,
        le: Optional[str] = None,
    ) -> str:
        if key == "__total__" and le is None:
            return ""
        parts = []
        if key != "__total__":
            parts.append(key)
        if le:
            parts.append(f'le="{le}"')
        return "{" + ",".join(parts) + "}"


def create_default_metrics() -> MetricsCollector:
    """
    Create and configure default metrics for the config platform.

    Returns:
        Configured MetricsCollector with standard metrics.
    """
    collector = MetricsCollector()

    # Reload counters
    collector.create_counter(
        "icyquant_config_reload_total",
        "Total number of configuration reload attempts",
    )
    collector.create_counter(
        "icyquant_config_reload_success_total",
        "Total number of successful configuration reloads",
    )
    collector.create_counter(
        "icyquant_config_reload_failure_total",
        "Total number of failed configuration reloads",
    )

    # Snapshot gauge
    collector.create_gauge(
        "icyquant_config_snapshot_version",
        "Current configuration snapshot version",
    )

    # Subscriber gauge
    collector.create_gauge(
        "icyquant_config_subscriber_total",
        "Total number of active configuration subscribers",
    )

    # Duration histogram
    collector.create_histogram(
        "icyquant_config_reload_duration_seconds",
        "Configuration reload duration in seconds",
        buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )

    return collector
