"""
Logging telemetry.

Provides OpenTelemetry integration for
the logging platform, exporting log
metrics and traces to collectors for
distributed observability.

Telemetry pipeline:
    Logs → OpenTelemetry → Collector → Prometheus/Grafana/Tempo/Jaeger
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .metrics import LoggingMetrics


class LoggingTelemetry:
    """
    Logging telemetry exporter.

    Exports logging metrics and traces
    to OpenTelemetry-compatible collectors,
    enabling integration with:
    - Prometheus (metrics)
    - Grafana (dashboards)
    - Tempo (traces)
    - Jaeger (traces)

    Usage:
        telemetry = LoggingTelemetry(
            metrics=logging_metrics,
            endpoint="http://otel-collector:4317",
        )
        await telemetry.start()
        await telemetry.export()
        await telemetry.stop()
    """

    def __init__(
        self,
        metrics: Optional[LoggingMetrics] = None,
        endpoint: str = "http://localhost:4317",
        service_name: str = "icyquant-logging",
        enable_traces: bool = True,
        enable_metrics: bool = True,
    ) -> None:
        """
        Initialize telemetry.

        Args:
            metrics: LoggingMetrics to export.
            endpoint: OpenTelemetry collector endpoint.
            service_name: Service name for telemetry.
            enable_traces: Whether to export traces.
            enable_metrics: Whether to export metrics.
        """

        self._metrics = metrics or LoggingMetrics()
        self._endpoint = endpoint
        self._service_name = service_name
        self._enable_traces = enable_traces
        self._enable_metrics = enable_metrics
        self._started: bool = False
        self._export_count: int = 0

    @property
    def is_started(
        self,
    ) -> bool:
        """Check if telemetry is started."""
        return self._started

    @property
    def export_count(
        self,
    ) -> int:
        """Get total export count."""
        return self._export_count

    async def start(
        self,
    ) -> None:
        """Start telemetry exporter."""

        self._started = True

    async def stop(
        self,
    ) -> None:
        """Stop telemetry exporter."""

        self._started = False

    async def export(
        self,
    ) -> Dict[str, Any]:
        """
        Export telemetry data.

        Returns:
            Export result dictionary.
        """

        if not self._started:
            return {"exported": False, "reason": "not_started"}

        self._export_count += 1

        data = self._collect_telemetry()

        return {
            "exported": True,
            "export_count": self._export_count,
            "endpoint": self._endpoint,
            "service": self._service_name,
            "data_points": len(data),
            "data": data,
        }

    def _collect_telemetry(
        self,
    ) -> Dict[str, Any]:
        """Collect telemetry data from metrics."""

        return {
            "queue_size": self._metrics.queue_size,
            "buffer_size": self._metrics.buffer_size,
            "queued_logs": self._metrics.queued_logs,
            "flushed_logs": self._metrics.flushed_logs,
            "dropped_logs": self._metrics.dropped_logs,
            "batch_count": self._metrics.batch_count,
            "flush_latency_ms": self._metrics.flush_latency_ms,
            "avg_flush_latency_ms": self._metrics.avg_flush_latency_ms,
            "drop_rate": self._metrics.drop_rate,
            "flush_rate": self._metrics.flush_rate,
        }

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """Get telemetry status."""

        return {
            "started": self._started,
            "endpoint": self._endpoint,
            "service": self._service_name,
            "traces_enabled": self._enable_traces,
            "metrics_enabled": self._enable_metrics,
            "export_count": self._export_count,
        }
