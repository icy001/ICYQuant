"""
Tracing platform bootstrap.

Provides a single entry point for initializing
and managing the entire tracing platform,
wiring together all components through
dependency injection.

Startup Sequence:

    Config
      |
      v
    Resource
      |
      v
    TracerProvider
      |
      v
    Sampler
      |
      v
    Span Processor
      |
      v
    Export Manager
      |
      v
    Instrumentation
      |
      v
    Tracing Service

Usage:
    bootstrap = TracingBootstrap(
        config=TracingConfig(),
    )

    # Add exporters before startup
    bootstrap.add_exporter(ConsoleExporter())

    # Add instrumentations
    bootstrap.add_instrumentation(FastAPIInstrumentation())

    await bootstrap.startup()

    # Access components
    service = bootstrap.service
    registry = bootstrap.registry

    # ... application runs ...

    await bootstrap.shutdown()
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .config import TracingConfig
from .exporters import ExportManager, TraceExporter
from .instrumentation import Instrumentation, InstrumentationManager
from .lifecycle import TracingLifecycle
from .monitoring import TracingMonitoring
from .processor import ProcessorFactory
from .provider import ICYTracerProvider
from .registry import TraceRegistry
from .sampler import (
    AlwaysOnSampler,
    ParentBasedSampler,
    RatioSampler,
    Sampler,
)
from .scheduler import TracingScheduler
from .service import TracingService
from .telemetry import TracingTelemetry


class TracingBootstrap:
    """
    Tracing platform bootstrap.

    Initializes and wires together all tracing
    components in the correct order:

    1. Config -> Configuration
    2. Resource -> OpenTelemetry Resource
    3. TracerProvider -> ICYTracerProvider
    4. Sampler -> Sampling strategy
    5. Span Processor -> Batch processor
    6. Export Manager -> Multi-exporter
    7. Instrumentation -> Auto-instrumentation
    8. Tracing Service -> Unified service

    All components are accessible as
    properties after initialization.

    Features:
    - One-click initialization
    - Ordered startup sequence
    - Graceful shutdown
    - Component injection
    - Health check aggregation
    - Hot reload support

    Usage:
        bootstrap = TracingBootstrap()

        # Configure before startup
        bootstrap.add_exporter(ConsoleExporter())
        bootstrap.add_instrumentation(FastAPIInstrumentation())

        await bootstrap.startup()

        # Access service
        service = bootstrap.service

        await bootstrap.shutdown()
    """

    def __init__(
        self,
        config: Optional[TracingConfig] = None,
        registry: Optional[TraceRegistry] = None,
        provider: Optional[ICYTracerProvider] = None,
        sampler: Optional[Sampler] = None,
        export_manager: Optional[ExportManager] = None,
        instrumentation_manager: Optional[InstrumentationManager] = None,
        enable_default_instrumentation: bool = False,
    ) -> None:
        """
        Initialize tracing bootstrap.

        Args:
            config: Tracing configuration.
            registry: Pre-configured TraceRegistry.
            provider: Pre-configured ICYTracerProvider.
            sampler: Pre-configured Sampler.
            export_manager: Pre-configured ExportManager.
            instrumentation_manager: Pre-configured InstrumentationManager.
            enable_default_instrumentation: Whether to add default instrumentations.
        """

        self._config = config or TracingConfig()

        # Core components (created if not provided)
        self._registry = registry or TraceRegistry()
        self._sampler = sampler or self._create_default_sampler()
        self._export_manager = export_manager or ExportManager(
            mode="broadcast"
        )
        self._instrumentation_manager = (
            instrumentation_manager or InstrumentationManager()
        )

        # Provider (created if not provided)
        self._provider = provider or ICYTracerProvider(
            config=self._config,
        )

        # Tracing service
        self._service = TracingService(
            provider=self._provider,
            registry=self._registry,
            exporter_manager=self._export_manager,
            instrumentation_manager=self._instrumentation_manager,
        )

        # Monitoring
        self._monitoring = TracingMonitoring(
            registry=self._registry,
            export_manager=self._export_manager,
            sampler=self._sampler,
        )

        # Scheduler
        self._scheduler = TracingScheduler(
            registry=self._registry,
            monitoring=self._monitoring,
            interval=30.0,
        )

        # Telemetry
        self._telemetry = TracingTelemetry(
            config=self._config,
        )

        # Lifecycle
        self._lifecycle = TracingLifecycle(
            service=self._service,
            scheduler=self._scheduler,
            config=self._config,
        )

        # Track initialized state
        self._initialized: bool = False

        # Add default instrumentations if requested
        if enable_default_instrumentation:
            self._add_default_instrumentations()

    def _create_default_sampler(
        self,
    ) -> Sampler:
        """Create default sampler based on config."""

        ratio = self._config.sample_ratio
        if ratio >= 1.0:
            return AlwaysOnSampler()
        elif ratio <= 0.0:
            from .sampler import AlwaysOffSampler
            return AlwaysOffSampler()
        else:
            return ParentBasedSampler(
                delegate=RatioSampler(ratio=ratio),
            )

    def _add_default_instrumentations(
        self,
    ) -> None:
        """Add default instrumentations."""

        try:
            from .instrumentation import (
                FastAPIInstrumentation,
                SQLAlchemyInstrumentation,
                RedisInstrumentation,
                KafkaInstrumentation,
                HTTPXInstrumentation,
                EventBusInstrumentation,
            )

            defaults = [
                FastAPIInstrumentation(),
                SQLAlchemyInstrumentation(),
                RedisInstrumentation(),
                KafkaInstrumentation(),
                HTTPXInstrumentation(),
                EventBusInstrumentation(),
            ]

            for inst in defaults:
                try:
                    self._instrumentation_manager.register_sync(
                        inst
                    ) if hasattr(
                        self._instrumentation_manager,
                        "register_sync",
                    ) else None
                except Exception:
                    pass
        except Exception:
            pass

    # === Properties ===

    @property
    def config(
        self,
    ) -> TracingConfig:
        """Get tracing configuration."""
        return self._config

    @property
    def provider(
        self,
    ) -> ICYTracerProvider:
        """Get tracer provider."""
        return self._provider

    @property
    def registry(
        self,
    ) -> TraceRegistry:
        """Get trace registry."""
        return self._registry

    @property
    def sampler(
        self,
    ) -> Sampler:
        """Get sampler."""
        return self._sampler

    @property
    def export_manager(
        self,
    ) -> ExportManager:
        """Get export manager."""
        return self._export_manager

    @property
    def instrumentation_manager(
        self,
    ) -> InstrumentationManager:
        """Get instrumentation manager."""
        return self._instrumentation_manager

    @property
    def service(
        self,
    ) -> TracingService:
        """Get tracing service."""
        return self._service

    @property
    def monitoring(
        self,
    ) -> TracingMonitoring:
        """Get monitoring."""
        return self._monitoring

    @property
    def scheduler(
        self,
    ) -> TracingScheduler:
        """Get scheduler."""
        return self._scheduler

    @property
    def telemetry(
        self,
    ) -> TracingTelemetry:
        """Get telemetry."""
        return self._telemetry

    @property
    def lifecycle(
        self,
    ) -> TracingLifecycle:
        """Get lifecycle manager."""
        return self._lifecycle

    @property
    def is_started(
        self,
    ) -> bool:
        """Check if bootstrap is started."""
        return self._lifecycle.is_started

    # === Convenience Methods ===

    def add_exporter(
        self,
        exporter: TraceExporter,
    ) -> None:
        """
        Register a trace exporter.

        Args:
            exporter: TraceExporter to register.
        """

        self._export_manager.register(exporter)
        self._registry.add_exporter(exporter)

    def add_instrumentation(
        self,
        instrumentation: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register an instrumentation.

        Note: This stores the instrumentation for
        later installation during startup.

        Args:
            instrumentation: Instrumentation to register.
            metadata: Optional metadata.
        """

        self._registry.add_instrumentation(instrumentation)

    def add_startup_hook(
        self,
        hook: Any,
    ) -> None:
        """
        Add a startup hook.

        Args:
            hook: Async callable.
        """

        self._lifecycle.add_startup_hook(hook)

    def add_shutdown_hook(
        self,
        hook: Any,
    ) -> None:
        """
        Add a shutdown hook.

        Args:
            hook: Async callable.
        """

        self._lifecycle.add_shutdown_hook(hook)

    # === Lifecycle ===

    async def startup(
        self,
    ) -> None:
        """
        Start the tracing platform.

        Initializes all components in order:
        1. Build TracerProvider
        2. Configure sampler
        3. Setup span processors
        4. Start export manager
        5. Install instrumentations
        6. Start tracing service
        7. Start scheduler
        """

        if self._initialized:
            return

        # Build provider (creates resource + TracerProvider)
        self._provider.build()

        # Register provider/tracer with registry
        self._registry.provider = self._provider
        self._registry.tracer_provider = self._provider.provider

        # Start telemetry
        await self._telemetry.startup()

        # Start lifecycle (service + scheduler)
        await self._lifecycle.startup()

        self._initialized = True

    async def shutdown(
        self,
    ) -> None:
        """
        Stop the tracing platform.

        Graceful shutdown ensures:
        - No span is lost
        - No trace is incomplete
        - Export is complete
        - Workers exit cleanly
        """

        if not self._initialized:
            return

        # Shutdown lifecycle (service + scheduler)
        await self._lifecycle.shutdown()

        # Shutdown telemetry
        await self._telemetry.shutdown()

        self._initialized = False

    async def reload(
        self,
        config: Optional[TracingConfig] = None,
    ) -> None:
        """
        Hot reload tracing configuration.

        Args:
            config: Optional new configuration.
        """

        await self._lifecycle.reload(config=config)

    # === Health & Status ===

    async def health_check(
        self,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive health check.

        Returns:
            Health status dictionary for all
            tracing components.
        """

        components: Dict[str, Any] = {}

        # Service health
        service_health = await self._service.health_check()
        components["service"] = service_health

        # Scheduler health
        components["scheduler"] = self._scheduler.get_status()

        # Telemetry health
        telemetry_health = await self._telemetry.health_check()
        components["telemetry"] = telemetry_health

        # Monitoring
        components["monitoring"] = self._monitoring.get_status()

        # Registry
        components["registry"] = self._registry.get_stats()

        # Export manager
        components["exporters"] = self._export_manager.get_stats()

        # Instrumentations
        components["instrumentations"] = (
            self._instrumentation_manager.get_status()
        )

        # Overall health
        all_healthy = (
            self._lifecycle.is_started
            and self._scheduler.error_count == 0
        )

        return {
            "healthy": all_healthy,
            "started": self._lifecycle.is_started,
            "components": components,
        }

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get complete tracing platform status.

        Returns:
            Status dictionary.
        """

        return {
            "initialized": self._initialized,
            "started": self._lifecycle.is_started,
            "config": {
                "service_name": self._config.service_name,
                "environment": self._config.environment,
                "enabled": self._config.enabled,
                "sample_ratio": self._config.sample_ratio,
                "exporter": self._config.exporter,
            },
            "service": self._service.get_status(),
            "scheduler": self._scheduler.get_status(),
            "telemetry": self._telemetry.get_status(),
            "monitoring": self._monitoring.get_status(),
            "lifecycle": self._lifecycle.get_status(),
            "registry": self._registry.get_stats(),
            "exporters": self._export_manager.get_stats(),
            "instrumentations": (
                self._instrumentation_manager.get_status()
            ),
        }
