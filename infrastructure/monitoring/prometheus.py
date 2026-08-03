"""
Prometheus registry.

Provides a unified Prometheus metrics
registry for the ICYQuant platform,
managing Counter, Gauge, and Histogram
metrics with consistent naming and
label conventions.

This is the single backend for all
ICYQuant metrics.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

try:
    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    CollectorRegistry = None  # type: ignore
    Counter = None  # type: ignore
    Gauge = None  # type: ignore
    Histogram = None  # type: ignore
    PROMETHEUS_AVAILABLE = False

from .labels import STANDARD_LABELS


class PrometheusRegistry:
    """
    Prometheus metrics registry.

    Central registry for all Prometheus
    metrics in the ICYQuant platform.
    Provides factory methods for creating
    Counter, Gauge, and Histogram metrics
    with consistent naming conventions.

    All metrics use the ``icyquant_`` prefix
    and follow Prometheus naming best practices.

    Usage:
        prom = PrometheusRegistry()

        counter = prom.counter(
            "orders_total",
            "Total orders placed",
            ["service", "module"],
        )
        counter.labels(service="trading").inc()

        gauge = prom.gauge(
            "active_connections",
            "Active DB connections",
            ["module"],
        )
        gauge.labels(module="database").set(42)

        histogram = prom.histogram(
            "query_duration_seconds",
            "Query duration",
            ["module"],
        )
        histogram.labels(module="database").observe(0.05)
    """

    def __init__(
        self,
        auto_register: bool = True,
    ) -> None:
        """
        Initialize Prometheus registry.

        Args:
            auto_register: Auto-register with default registry.
        """

        self._available = PROMETHEUS_AVAILABLE
        self._registry = (
            CollectorRegistry()
            if PROMETHEUS_AVAILABLE
            else None
        )
        self._metrics: Dict[str, Any] = {}
        self._counters: Dict[str, Any] = {}
        self._gauges: Dict[str, Any] = {}
        self._histograms: Dict[str, Any] = {}

        if not self._available:
            import warnings

            warnings.warn(
                "prometheus_client not installed. "
                "Install with: pip install prometheus-client"
            )

    @property
    def is_available(
        self,
    ) -> bool:
        """Check if Prometheus client is available."""
        return self._available

    @property
    def registry(
        self,
    ) -> Optional[CollectorRegistry]:
        """Get the underlying Prometheus registry."""
        return self._registry

    @property
    def metrics(
        self,
    ) -> Dict[str, Any]:
        """Get all registered metrics."""
        return self._metrics

    @property
    def counter_count(
        self,
    ) -> int:
        """Get number of registered counters."""
        return len(self._counters)

    @property
    def gauge_count(
        self,
    ) -> int:
        """Get number of registered gauges."""
        return len(self._gauges)

    @property
    def histogram_count(
        self,
    ) -> int:
        """Get number of registered histograms."""
        return len(self._histograms)

    def counter(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
    ) -> Any:
        """
        Create or get a Counter metric.

        Counters only increase (use _total suffix
        by convention).

        Args:
            name: Metric name (will be prefixed with icyquant_).
            description: Help text for the metric.
            labels: Label names for the metric.

        Returns:
            prometheus_client.Counter instance.
        """

        full_name = self._make_name(name)

        if full_name in self._counters:
            return self._counters[full_name]

        if not self._available or Counter is None:
            return _MockMetric(full_name)

        metric = Counter(
            full_name,
            description,
            labelnames=labels or [],
            registry=self._registry,
        )
        self._counters[full_name] = metric
        self._metrics[full_name] = metric
        return metric

    def gauge(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
    ) -> Any:
        """
        Create or get a Gauge metric.

        Gauges can go up and down.

        Args:
            name: Metric name (will be prefixed with icyquant_).
            description: Help text for the metric.
            labels: Label names for the metric.

        Returns:
            prometheus_client.Gauge instance.
        """

        full_name = self._make_name(name)

        if full_name in self._gauges:
            return self._gauges[full_name]

        if not self._available or Gauge is None:
            return _MockMetric(full_name)

        metric = Gauge(
            full_name,
            description,
            labelnames=labels or [],
            registry=self._registry,
        )
        self._gauges[full_name] = metric
        self._metrics[full_name] = metric
        return metric

    def histogram(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
        buckets: Optional[List[float]] = None,
    ) -> Any:
        """
        Create or get a Histogram metric.

        Histograms track distribution of values.
        Use _seconds suffix for durations.

        Args:
            name: Metric name (will be prefixed with icyquant_).
            description: Help text for the metric.
            labels: Label names for the metric.
            buckets: Custom bucket boundaries.

        Returns:
            prometheus_client.Histogram instance.
        """

        full_name = self._make_name(name)

        if full_name in self._histograms:
            return self._histograms[full_name]

        if not self._available or Histogram is None:
            return _MockMetric(full_name)

        kwargs: dict = {
            "labelnames": labels or [],
            "registry": self._registry,
        }
        if buckets:
            kwargs["buckets"] = buckets

        metric = Histogram(
            full_name,
            description,
            **kwargs,
        )
        self._histograms[full_name] = metric
        self._metrics[full_name] = metric
        return metric

    def register_custom(
        self,
        name: str,
        metric: Any,
    ) -> Any:
        """
        Register a custom metric directly.

        Args:
            name: Metric name.
            metric: Prometheus metric instance.

        Returns:
            The registered metric.
        """

        self._metrics[name] = metric
        return metric

    def get_counter(
        self,
        name: str,
    ) -> Optional[Any]:
        """Get a registered counter by name."""
        return self._counters.get(
            self._make_name(name)
        )

    def get_gauge(
        self,
        name: str,
    ) -> Optional[Any]:
        """Get a registered gauge by name."""
        return self._gauges.get(
            self._make_name(name)
        )

    def get_histogram(
        self,
        name: str,
    ) -> Optional[Any]:
        """Get a registered histogram by name."""
        return self._histograms.get(
            self._make_name(name)
        )

    def generate_metrics(
        self,
    ) -> str:
        """
        Generate Prometheus text exposition format.

        Returns:
            Prometheus text format string.
        """

        if not self._available or generate_latest is None:
            return ""
        result = generate_latest(self._registry)
        if isinstance(result, bytes):
            return result.decode("utf-8")
        return str(result)

    def unregister(
        self,
        metric: Any,
    ) -> None:
        """
        Unregister a metric from the registry.

        Args:
            metric: Metric to unregister.
        """

        if self._registry:
            try:
                self._registry.unregister(metric)
            except Exception:
                pass

    def _make_name(
        self,
        name: str,
    ) -> str:
        """
        Build fully qualified metric name.

        Args:
            name: Base metric name.

        Returns:
            Name with icyquant_ prefix.
        """

        if name.startswith("icyquant_"):
            return name
        return f"icyquant_{name}"

    def get_all_metric_names(
        self,
    ) -> List[str]:
        """Get list of all registered metric names."""
        return list(self._metrics.keys())

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get registry status.

        Returns:
            Status dictionary with counts.
        """

        return {
            "available": self._available,
            "total_metrics": len(self._metrics),
            "counters": len(self._counters),
            "gauges": len(self._gauges),
            "histograms": len(self._histograms),
        }


class _MockMetric:
    """
    Mock metric for when prometheus_client is
    not available. Provides safe no-op behavior.
    """

    def __init__(
        self,
        name: str,
    ) -> None:
        self._name = name
        self._value: float = 0

    def labels(
        self,
        **kwargs: Any,
    ) -> "_MockMetric":
        return self

    def inc(
        self,
        amount: float = 1,
    ) -> None:
        self._value += amount

    def dec(
        self,
        amount: float = 1,
    ) -> None:
        self._value -= amount

    def set(
        self,
        value: float,
    ) -> None:
        self._value = value

    def observe(
        self,
        value: float,
    ) -> None:
        pass

    def get(
        self,
    ) -> float:
        return self._value
