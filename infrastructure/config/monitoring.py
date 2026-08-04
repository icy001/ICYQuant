"""
Configuration monitoring.

Integrates the configuration platform with
the monitoring system, providing real-time
metrics and alerting.

Metrics:
- icyquant_config_snapshot_total
- icyquant_config_reload_total
- icyquant_config_reload_latency_seconds
- icyquant_config_watcher_events_total
- icyquant_config_validation_failure_total
- icyquant_config_active_snapshot
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .dynamic.metrics import MetricsCollector, create_default_metrics

logger = logging.getLogger(__name__)


class ConfigurationMonitor:
    """
    Configuration platform monitor.

    Collects and exposes metrics for the configuration
    platform, integrating with the metrics collector
    to provide real-time monitoring.

    Metrics Collected:
    - Snapshot count and version
    - Reload count, success, failure, latency
    - Watcher event count
    - Validation failure count
    - Active subscriber count

    Usage:
        monitor = ConfigurationMonitor()
        monitor.record_reload(success=True, duration=0.05)
        monitor.record_watcher_event()
        prom = monitor.get_prometheus_metrics()
    """

    def __init__(
        self,
        metrics: Optional[MetricsCollector] = None,
    ) -> None:
        """
        Initialize monitor.

        Args:
            metrics: Custom metrics collector.
        """
        self._metrics = metrics or create_default_metrics()
        self._alerts: List[Dict[str, Any]] = []
        self._max_alerts = 100
        self._lock = threading.Lock()

        # Alert thresholds
        self._thresholds = {
            "reload_failure_rate": 0.3,      # Alert if >30% failure
            "reload_latency_p99": 5.0,       # Alert if >5s
            "validation_failure_count": 10,   # Alert if >10 failures
        }

        # Alert callbacks
        self._alert_callbacks: List[Callable] = []

    @property
    def metrics(
        self,
    ) -> MetricsCollector:
        """Get metrics collector."""
        return self._metrics

    # ── Recording Methods ──

    def record_reload(
        self,
        success: bool,
        duration: float,
        changed_keys: Optional[List[str]] = None,
    ) -> None:
        """
        Record a reload event.

        Args:
            success: Whether reload succeeded.
            duration: Reload duration in seconds.
            changed_keys: List of changed keys.
        """
        self._metrics.inc_counter("icyquant_config_reload_total")

        if success:
            self._metrics.inc_counter("icyquant_config_reload_success_total")
        else:
            self._metrics.inc_counter("icyquant_config_reload_failure_total")

        self._metrics.observe_histogram(
            "icyquant_config_reload_duration_seconds", duration
        )

        # Check latency threshold
        if duration > self._thresholds["reload_latency_p99"]:
            self._raise_alert(
                "high_latency",
                f"Reload took {duration:.2f}s (threshold: {self._thresholds['reload_latency_p99']}s)",
            )

    def record_snapshot(
        self,
        version: int,
        key_count: int = 0,
    ) -> None:
        """Record snapshot creation."""
        self._metrics.inc_counter("icyquant_config_snapshot_total")
        self._metrics.set_gauge("icyquant_config_active_snapshot", version)

    def record_watcher_event(
        self,
        source: str = "file",
    ) -> None:
        """Record a watcher event."""
        self._metrics.inc_counter(
            "icyquant_config_watcher_events_total",
            labels={"source": source},
        )

    def record_validation_failure(
        self,
        errors: List[str],
    ) -> None:
        """Record validation failures."""
        for _ in errors:
            self._metrics.inc_counter("icyquant_config_validation_failure_total")

        if len(errors) > self._thresholds["validation_failure_count"]:
            self._raise_alert(
                "validation_failures",
                f"Validation failure count {len(errors)} exceeds threshold",
            )

    def record_subscriber_count(
        self,
        count: int,
    ) -> None:
        """Record subscriber count."""
        self._metrics.set_gauge("icyquant_config_subscriber_total", count)

    # ── Alert Management ──

    def add_alert_callback(
        self,
        callback: Callable,
    ) -> None:
        """Add an alert callback."""
        self._alert_callbacks.append(callback)

    def set_threshold(
        self,
        name: str,
        value: float,
    ) -> None:
        """Set an alert threshold."""
        self._thresholds[name] = value

    def _raise_alert(
        self,
        alert_type: str,
        message: str,
    ) -> None:
        """Raise an alert."""
        alert = {
            "type": alert_type,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }

        with self._lock:
            self._alerts.append(alert)
            if len(self._alerts) > self._max_alerts:
                self._alerts.pop(0)

        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception:
                pass

    def get_alerts(
        self,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get recent alerts."""
        with self._lock:
            return self._alerts[-limit:]

    # ── Export ──

    def get_all_metrics(
        self,
    ) -> Dict[str, Any]:
        """Get all collected metrics."""
        return self._metrics.get_all_metrics()

    def get_prometheus_metrics(
        self,
    ) -> str:
        """Get Prometheus-format metrics."""
        return self._metrics.get_prometheus_format()

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """Get monitoring status."""
        all_metrics = self._metrics.get_all_metrics()
        return {
            "alert_count": len(self._alerts),
            "thresholds": self._thresholds,
            "counter_count": len(all_metrics.get("counters", {})),
            "gauge_count": len(all_metrics.get("gauges", {})),
            "histogram_count": len(all_metrics.get("histograms", {})),
        }
