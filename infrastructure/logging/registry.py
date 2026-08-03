"""
Logging metric registry.

Handles registration of logging metrics
with the monitoring platform's Prometheus
registry, enabling unified observability.

Metrics registered:
- icyquant_logging_queue_size
- icyquant_logging_flush_total
- icyquant_logging_batch_total
- icyquant_logging_drop_total
- icyquant_logging_flush_latency_seconds
- icyquant_logging_worker_status
"""

from __future__ import annotations

from typing import Any, Optional

from .metrics import LoggingMetrics


class LoggingRegistry:
    """
    Logging metric registry.

    Bridges logging metrics to the
    monitoring platform's Prometheus
    registry.

    Usage:
        registry = LoggingRegistry(
            prometheus=prom_registry,
            metrics=logging_metrics,
        )
        registry.register_metrics()
        registry.update_metrics()
    """

    # Metric names
    QUEUE_SIZE = "icyquant_logging_queue_size"
    FLUSH_TOTAL = "icyquant_logging_flush_total"
    BATCH_TOTAL = "icyquant_logging_batch_total"
    DROP_TOTAL = "icyquant_logging_drop_total"
    FLUSH_LATENCY = "icyquant_logging_flush_latency_seconds"
    WORKER_STATUS = "icyquant_logging_worker_status"

    def __init__(
        self,
        prometheus: Any = None,
        metrics: Optional[LoggingMetrics] = None,
    ) -> None:
        """
        Initialize registry.

        Args:
            prometheus: PrometheusRegistry instance.
            metrics: LoggingMetrics to register.
        """

        self._prometheus = prometheus
        self._metrics = metrics or LoggingMetrics()
        self._registered: bool = False

        # Prometheus metric objects
        self._queue_gauge: Any = None
        self._flush_counter: Any = None
        self._batch_counter: Any = None
        self._drop_counter: Any = None
        self._latency_gauge: Any = None
        self._worker_gauge: Any = None

    @property
    def metrics(
        self,
    ) -> LoggingMetrics:
        """Get logging metrics."""
        return self._metrics

    def register_metrics(
        self,
    ) -> None:
        """Register all logging metrics with Prometheus."""

        if self._prometheus is None or self._registered:
            return

        self._queue_gauge = self._prometheus.gauge(
            self.QUEUE_SIZE,
            "Current log queue size",
            ["service"],
        )

        self._flush_counter = self._prometheus.counter(
            self.FLUSH_TOTAL,
            "Total logs flushed",
            ["service"],
        )

        self._batch_counter = self._prometheus.counter(
            self.BATCH_TOTAL,
            "Total batches processed",
            ["service"],
        )

        self._drop_counter = self._prometheus.counter(
            self.DROP_TOTAL,
            "Total logs dropped",
            ["service"],
        )

        self._latency_gauge = self._prometheus.gauge(
            self.FLUSH_LATENCY,
            "Log flush latency in seconds",
            ["service"],
        )

        self._worker_gauge = self._prometheus.gauge(
            self.WORKER_STATUS,
            "Log worker status (1=running, 0=stopped)",
            ["service"],
        )

        self._registered = True

    def update_metrics(
        self,
        service: str = "icyquant",
    ) -> None:
        """
        Update Prometheus metrics from LoggingMetrics.

        Args:
            service: Service label value.
        """

        if not self._registered:
            return

        labels = {"service": service}

        if self._queue_gauge is not None:
            self._queue_gauge.labels(**labels).set(
                self._metrics.queue_size
            )

        if self._flush_counter is not None:
            self._flush_counter.labels(**labels).inc(
                self._metrics.flushed_logs
            )

        if self._batch_counter is not None:
            self._batch_counter.labels(**labels).inc(
                self._metrics.batch_count
            )

        if self._drop_counter is not None:
            self._drop_counter.labels(**labels).inc(
                self._metrics.dropped_logs
            )

        if self._latency_gauge is not None:
            self._latency_gauge.labels(**labels).set(
                self._metrics.flush_latency_ms / 1000.0
            )

    def set_worker_status(
        self,
        running: bool,
        service: str = "icyquant",
    ) -> None:
        """
        Set worker status metric.

        Args:
            running: Whether worker is running.
            service: Service label value.
        """

        if self._worker_gauge is not None:
            self._worker_gauge.labels(
                service=service
            ).set(1 if running else 0)

    def get_status(
        self,
    ) -> dict:
        """Get registry status."""

        return {
            "registered": self._registered,
            "metrics": self._metrics.to_dict(),
            "prometheus": self._prometheus is not None,
        }
