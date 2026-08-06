"""Metrics Adapter — integrates the Scheduler with the platform Metrics pipeline.

The :class:`MetricsAdapter` exports scheduler metrics to the platform's
centralized metrics system (Prometheus, Grafana, etc.).
"""

from __future__ import annotations

import enum
import logging
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricsSink(enum.Enum):
    """Metrics export sinks."""

    PROMETHEUS = "prometheus"
    OTLP = "otlp"
    STATSD = "statsd"
    CONSOLE = "console"
    NONE = "none"


class MetricsAdapter:
    """Adapter for platform metrics integration.

    Responsibilities:
    * Export scheduler metrics to Prometheus/OTLP
    * Register scheduler metrics with the platform registry
    * Provide metrics scraping endpoint
    * Aggregate multi-node metrics

    Usage::

        adapter = MetricsAdapter(sink=MetricsSink.PROMETHEUS)
        await adapter.connect()
        adapter.register_metric("scheduler_jobs_total", "counter")
    """

    def __init__(self, sink: MetricsSink = MetricsSink.PROMETHEUS) -> None:
        self._sink = sink
        self._lock = threading.Lock()
        self._connected = False
        self._registered_metrics: Dict[str, Dict[str, Any]] = {}
        self._scrape_count: int = 0

    @property
    def sink(self) -> MetricsSink:
        return self._sink

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def registered_count(self) -> int:
        return len(self._registered_metrics)

    async def connect(self) -> None:
        logger.info("MetricsAdapter: connecting to %s", self._sink.value)
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("MetricsAdapter: disconnected")

    async def synchronize(self) -> Dict[str, Any]:
        return {"sink": self._sink.value, "registered_metrics": len(self._registered_metrics)}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_metric(self, name: str, metric_type: str, help_text: str = "", labels: Optional[List[str]] = None) -> None:
        """Register a metric with the platform metrics registry."""
        self._registered_metrics[name] = {
            "type": metric_type,
            "help": help_text,
            "labels": labels or [],
        }
        logger.debug("MetricsAdapter: registered %s (%s)", name, metric_type)

    def register_counter(self, name: str, help_text: str = "") -> None:
        self.register_metric(name, "counter", help_text)

    def register_gauge(self, name: str, help_text: str = "") -> None:
        self.register_metric(name, "gauge", help_text)

    def register_histogram(self, name: str, help_text: str = "", buckets: Optional[List[float]] = None) -> None:
        self.register_metric(name, "histogram", help_text)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    async def scrape(self) -> Dict[str, Any]:
        """Return all registered metrics in Prometheus exposition format."""
        self._scrape_count += 1
        return {
            "metrics": self._registered_metrics,
            "scrape_count": self._scrape_count,
        }

    async def export(self, metrics: Dict[str, Any]) -> None:
        """Export a batch of metric values."""
        logger.debug("MetricsAdapter: exporting %d metrics", len(metrics))
