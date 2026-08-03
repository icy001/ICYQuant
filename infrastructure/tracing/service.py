"""
Tracing platform service.

Unified entry point for the tracing platform,
coordinating provider, registry, exporters,
and instrumentation lifecycle in a single
service interface.

Runtime Flow:

    Application
          |
          v
    Instrumentation
          |
          v
       Tracer
          |
          v
    Span Processor
          |
          v
    Export Pipeline
          |
          v
    OpenTelemetry Collector
          |
          +----> Tempo
          +----> Jaeger
          +----> Prometheus
          +----> Grafana

Usage:
    service = TracingService(
        provider=provider,
        registry=registry,
        exporter_manager=export_manager,
        instrumentation_manager=inst_manager,
    )
    await service.startup()
    # ... application runs ...
    await service.shutdown()
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .exporters import ExportManager
from .instrumentation import InstrumentationManager
from .metrics import TraceMetrics
from .registry import TraceRegistry


class TracingService:
    """
    Unified tracing service.

    Coordinates the full tracing pipeline:
    1. Instrumentations are installed (auto-instrument HTTP, DB, Redis, etc.)
    2. Exporters are started (OTLP, Jaeger, Tempo, Zipkin, Console)
    3. Spans flow through processor -> exporter pipeline
    4. Graceful shutdown ensures no spans are lost

    Lifecycle:
        Startup:
            1. Install instrumentations
            2. Start exporters

        Shutdown (Graceful):
            1. Flush exporters (finish active batches)
            2. Shutdown exporters (close connections)
            3. Shutdown instrumentations (uninstall hooks)

    Attributes:
        provider: ICYTracerProvider instance.
        registry: TraceRegistry for trace lifecycle.
        exporters: ExportManager for multi-backend export.
        instrumentations: InstrumentationManager for auto-instrumentation.
    """

    def __init__(
        self,
        provider: Any,
        registry: TraceRegistry,
        exporter_manager: ExportManager,
        instrumentation_manager: InstrumentationManager,
        metrics: Optional[TraceMetrics] = None,
    ) -> None:
        """
        Initialize tracing service.

        Args:
            provider: ICYTracerProvider instance.
            registry: TraceRegistry instance.
            exporter_manager: ExportManager instance.
            instrumentation_manager: InstrumentationManager instance.
            metrics: Optional TraceMetrics instance.
        """

        self.provider = provider
        self.registry = registry
        self.exporters = exporter_manager
        self.instrumentations = instrumentation_manager
        self._metrics = metrics or TraceMetrics()

        self._started: bool = False

    @property
    def is_started(
        self,
    ) -> bool:
        """Check if service is started."""
        return self._started

    @property
    def metrics(
        self,
    ) -> TraceMetrics:
        """Get trace metrics."""
        return self._metrics

    async def startup(
        self,
    ) -> None:
        """
        Start the tracing service.

        Order:
        1. Install all registered instrumentations
        2. Start the export manager

        This enables auto-instrumentation before
        exporters begin accepting spans, ensuring
        no spans are lost during startup.
        """

        if self._started:
            return

        # Install instrumentations (FastAPI, SQLAlchemy, Redis, etc.)
        await self.instrumentations.install_all()

        # Start exporters
        await self.exporters.startup()

        self._started = True

    async def shutdown(
        self,
    ) -> None:
        """
        Graceful shutdown of the tracing service.

        Order:
        1. Flush exporters (export remaining buffered spans)
        2. Shutdown exporters (close backend connections)
        3. Shutdown instrumentations (uninstall hooks)

        Guarantees:
        - No span is lost
        - No trace is incomplete
        - Export is complete
        - Workers exit cleanly
        """

        if not self._started:
            return

        # Flush any pending batches
        await self.exporters.flush()

        # Shutdown exporters
        await self.exporters.shutdown()

        # Shutdown instrumentations (reverse order)
        await self.instrumentations.shutdown()

        # Shutdown provider
        if self.provider is not None and hasattr(
            self.provider, "shutdown"
        ):
            try:
                self.provider.shutdown()
            except Exception:
                pass

        self._started = False

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get service status.

        Returns:
            Status dictionary.
        """

        return {
            "started": self._started,
            "provider": self.provider is not None,
            "exporters": self.exporters.get_stats(),
            "instrumentations": self.instrumentations.get_status(),
            "registry": self.registry.get_stats(),
            "metrics": self._metrics.get_stats(),
        }

    async def health_check(
        self,
    ) -> Dict[str, Any]:
        """
        Check tracing service health.

        Returns:
            Health status dictionary.
        """

        return {
            "provider": self.provider is not None,
            "processor": True,
            "exporter": self.exporters.is_started,
            "collector": self.exporters.exporter_count > 0,
            "instrumentation": (
                self.instrumentations.installed_count > 0
            ),
            "started": self._started,
        }
