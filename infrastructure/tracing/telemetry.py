"""
Tracing telemetry integration.

Connects the tracing platform to the unified
OpenTelemetry Collector pipeline, enabling
end-to-end observability across the ICYQuant
platform.

Unified Observability Flow:

    Trace
      |
      v
    OTLP
      |
      v
    OpenTelemetry Collector
      |
      +----> Tempo (traces)
      +----> Jaeger (traces)
      +----> Prometheus (metrics)
      +----> Grafana (visualization)

Unified Pillars:
    Business Request
        |
        v
    Trace ------------------+
        |                   |
        v                   v
    Logs                Metrics
        |                   |
        +-------+-----------+
                |
                v
        Unified Dashboard

A single trading request can be traced through:
    Trace -> Strategy -> Risk -> OMS -> Execution -> Ledger
    With all corresponding logs and metrics correlated
    via the trace context.

Usage:
    telemetry = TracingTelemetry(
        exporter_type="otlp",
        endpoint="localhost:4317",
    )
    await telemetry.startup()
    # ... traces flow to collector ...
    await telemetry.shutdown()
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .config import TracingConfig
from .exporters import ExporterFactory, TraceExporter


class TracingTelemetry:
    """
    Unified tracing telemetry.

    Manages the connection between the tracing
    platform and the OpenTelemetry Collector,
    enabling unified observability across traces,
    logs, and metrics.

    Features:
    - OTLP export to OpenTelemetry Collector
    - Multi-backend support (Tempo, Jaeger, Grafana)
    - Trace context correlation with logs
    - Trace context correlation with metrics (exemplars)
    - Correlation ID injection for log linking

    Backends:
    - Tempo: Grafana's trace backend
    - Jaeger: Distributed tracing UI
    - Prometheus: Metrics with exemplars
    - Grafana: Unified visualization

    Usage:
        telemetry = TracingTelemetry(
            config=TracingConfig(exporter="otlp"),
        )
        await telemetry.startup()
        # Traces flow to OTLP collector
        await telemetry.shutdown()
    """

    def __init__(
        self,
        config: Optional[TracingConfig] = None,
        exporters: Optional[List[TraceExporter]] = None,
        collector_endpoint: Optional[str] = None,
    ) -> None:
        """
        Initialize telemetry.

        Args:
            config: Tracing configuration.
            exporters: Pre-configured exporters list.
            collector_endpoint: OTLP collector endpoint.
        """

        self._config = config or TracingConfig()
        self._collector_endpoint = collector_endpoint or (
            "localhost:4317"
        )
        self._exporters: List[TraceExporter] = (
            exporters or []
        )
        self._started: bool = False

        # Correlation tracking
        self._correlation_count: int = 0
        self._log_correlation_count: int = 0
        self._metric_correlation_count: int = 0

    @property
    def is_started(
        self,
    ) -> bool:
        """Check if telemetry is started."""
        return self._started

    @property
    def exporter_count(
        self,
    ) -> int:
        """Get exporter count."""
        return len(self._exporters)

    @property
    def collector_endpoint(
        self,
    ) -> str:
        """Get collector endpoint."""
        return self._collector_endpoint

    def add_exporter(
        self,
        exporter: TraceExporter,
    ) -> None:
        """
        Add an exporter.

        Args:
            exporter: TraceExporter to add.
        """

        self._exporters.append(exporter)

    def add_default_exporters(
        self,
    ) -> None:
        """
        Add default exporters based on config.

        Creates exporters for the configured
        backends (OTLP, Jaeger, Tempo, etc.).
        """

        exporter_type = self._config.exporter

        if exporter_type == "none":
            return

        try:
            exporter = ExporterFactory.create(
                exporter_type,
                endpoint=self._collector_endpoint,
            )
            self._exporters.append(exporter)
        except Exception:
            pass

    async def startup(
        self,
    ) -> None:
        """
        Start telemetry.

        Initializes exporters and begins
        accepting trace data for export.
        """

        if self._started:
            return

        # Add default exporters if none configured
        if not self._exporters:
            self.add_default_exporters()

        self._started = True

    async def shutdown(
        self,
    ) -> None:
        """
        Shutdown telemetry.

        Flushes and shuts down all exporters.
        """

        if not self._started:
            return

        for exporter in self._exporters:
            try:
                await exporter.flush()
            except Exception:
                pass

        for exporter in self._exporters:
            try:
                await exporter.shutdown()
            except Exception:
                pass

        self._started = False

    def record_correlation(
        self,
        target: str = "log",
    ) -> None:
        """
        Record a trace correlation.

        Args:
            target: Correlation target ("log" or "metric").
        """

        self._correlation_count += 1
        if target == "log":
            self._log_correlation_count += 1
        elif target == "metric":
            self._metric_correlation_count += 1

    def get_correlation_id(
        self,
        trace_id: str,
        span_id: Optional[str] = None,
    ) -> str:
        """
        Generate a correlation ID for log linking.

        Args:
            trace_id: Trace ID.
            span_id: Optional span ID.

        Returns:
            Correlation ID string.
        """

        self.record_correlation(target="log")
        if span_id:
            return f"{trace_id}:{span_id}"
        return trace_id

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get telemetry status.

        Returns:
            Status dictionary.
        """

        return {
            "started": self._started,
            "collector_endpoint": self._collector_endpoint,
            "exporter_count": self.exporter_count,
            "correlation_count": self._correlation_count,
            "log_correlation_count": self._log_correlation_count,
            "metric_correlation_count": (
                self._metric_correlation_count
            ),
            "config": {
                "service_name": self._config.service_name,
                "environment": self._config.environment,
                "exporter": self._config.exporter,
                "sample_ratio": self._config.sample_ratio,
            },
        }

    async def health_check(
        self,
    ) -> Dict[str, Any]:
        """
        Check telemetry health.

        Returns:
            Health status dictionary.
        """

        return {
            "started": self._started,
            "collector": self._collector_endpoint is not None,
            "exporters": self.exporter_count > 0,
            "correlation_enabled": True,
        }
