"""
Platform Metrics — Prometheus-compatible metrics for the Strategy Platform.

Exposes deployment, canary, rollback, runtime, event, and audit
metrics for monitoring dashboards and alerting systems.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MetricValue:
    """A single metric observation."""
    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metric_type: str = "counter"  # counter, gauge, histogram, summary
    help_text: str = ""


class PlatformMetrics:
    """
    Platform-level metrics collection and export.

    Tracks all strategy platform operations through Prometheus-style
    counters, gauges, and histograms for real-time monitoring.

    Metrics:
        icyquant_strategy_deployments_total
        icyquant_strategy_canary_total
        icyquant_strategy_rollbacks_total
        icyquant_strategy_runtime_latency
        icyquant_strategy_events_total
        icyquant_strategy_audit_records
        icyquant_strategy_api_requests_total
    """

    # Metric name constants
    DEPLOYMENTS_TOTAL = "icyquant_strategy_deployments_total"
    CANARY_TOTAL = "icyquant_strategy_canary_total"
    ROLLBACKS_TOTAL = "icyquant_strategy_rollbacks_total"
    RUNTIME_LATENCY = "icyquant_strategy_runtime_latency"
    EVENTS_TOTAL = "icyquant_strategy_events_total"
    AUDIT_RECORDS = "icyquant_strategy_audit_records"
    API_REQUESTS_TOTAL = "icyquant_strategy_api_requests_total"
    STRATEGIES_ACTIVE = "icyquant_strategies_active"
    ADAPTER_LATENCY = "icyquant_adapter_latency"
    EVENT_BRIDGE_THROUGHPUT = "icyquant_event_bridge_throughput"

    def __init__(self) -> None:
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._metric_definitions: dict[str, MetricValue] = {}

        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default metric definitions."""
        defaults = [
            MetricValue(name=self.DEPLOYMENTS_TOTAL, value=0, metric_type="counter",
                        help_text="Total number of strategy deployments"),
            MetricValue(name=self.CANARY_TOTAL, value=0, metric_type="counter",
                        help_text="Total number of canary deployments"),
            MetricValue(name=self.ROLLBACKS_TOTAL, value=0, metric_type="counter",
                        help_text="Total number of strategy rollbacks"),
            MetricValue(name=self.RUNTIME_LATENCY, value=0, metric_type="histogram",
                        help_text="Strategy runtime latency in milliseconds"),
            MetricValue(name=self.EVENTS_TOTAL, value=0, metric_type="counter",
                        help_text="Total number of strategy events processed"),
            MetricValue(name=self.AUDIT_RECORDS, value=0, metric_type="gauge",
                        help_text="Number of audit records stored"),
            MetricValue(name=self.API_REQUESTS_TOTAL, value=0, metric_type="counter",
                        help_text="Total number of API requests served"),
            MetricValue(name=self.STRATEGIES_ACTIVE, value=0, metric_type="gauge",
                        help_text="Number of currently active strategies"),
            MetricValue(name=self.ADAPTER_LATENCY, value=0, metric_type="histogram",
                        help_text="Adapter call latency in milliseconds"),
            MetricValue(name=self.EVENT_BRIDGE_THROUGHPUT, value=0, metric_type="gauge",
                        help_text="Event bridge events per second"),
        ]
        for m in defaults:
            self._metric_definitions[m.name] = m

    # ---- Counter Operations ----

    def increment(self, name: str, amount: float = 1.0, labels: Optional[dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        if name not in self._counters:
            self._counters[name] = 0
        self._counters[name] += amount
        logger.debug(f"Metric incremented: {name} += {amount}")

    def get_counter(self, name: str) -> float:
        """Get a counter value."""
        return self._counters.get(name, 0.0)

    # ---- Gauge Operations ----

    def set_gauge(self, name: str, value: float, labels: Optional[dict[str, str]] = None) -> None:
        """Set a gauge metric."""
        self._gauges[name] = value

    def get_gauge(self, name: str) -> float:
        """Get a gauge value."""
        return self._gauges.get(name, 0.0)

    # ---- Histogram Operations ----

    def observe(self, name: str, value: float) -> None:
        """Record a histogram observation."""
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)
        if len(self._histograms[name]) > 10000:
            self._histograms[name] = self._histograms[name][-10000:]

    def get_histogram_stats(self, name: str) -> Optional[dict[str, float]]:
        """Get histogram statistics."""
        values = self._histograms.get(name, [])
        if not values:
            return None
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        return {
            "count": n,
            "sum": sum(sorted_vals),
            "min": min(sorted_vals),
            "max": max(sorted_vals),
            "avg": sum(sorted_vals) / n,
            "p50": sorted_vals[int(n * 0.5)],
            "p95": sorted_vals[int(n * 0.95)],
            "p99": sorted_vals[int(n * 0.99)],
        }

    # ---- Deployment Metrics ----

    def record_deployment(self, strategy_id: str, status: str) -> None:
        """Record a deployment event."""
        self.increment(self.DEPLOYMENTS_TOTAL)

    def record_canary(self, strategy_id: str) -> None:
        """Record a canary deployment."""
        self.increment(self.CANARY_TOTAL)

    def record_rollback(self, strategy_id: str) -> None:
        """Record a rollback."""
        self.increment(self.ROLLBACKS_TOTAL)

    def record_runtime_latency(self, latency_ms: float) -> None:
        """Record a runtime latency observation."""
        self.observe(self.RUNTIME_LATENCY, latency_ms)

    def record_event(self) -> None:
        """Record an event processed."""
        self.increment(self.EVENTS_TOTAL)

    def record_api_request(self) -> None:
        """Record an API request."""
        self.increment(self.API_REQUESTS_TOTAL)

    # ---- Snapshot ----

    def snapshot(self) -> dict[str, Any]:
        """Get a snapshot of all metrics."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {name: self.get_histogram_stats(name) for name in self._histograms},
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        logger.info("Platform metrics reset.")
