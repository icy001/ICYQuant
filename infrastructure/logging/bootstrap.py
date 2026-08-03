"""
Logging bootstrap.

Provides unified initialization and
lifecycle management for the entire
logging platform, wiring together all
components via the DI container.

Usage:
    bootstrap = LoggingBootstrap(
        config=LoggingConfig(level="DEBUG"),
    )
    bootstrap.add_handler(ConsoleHandler())

    await bootstrap.startup()

    logger = bootstrap.get_logger("strategy")
    logger.info("Order submitted", symbol="AAPL")

    await bootstrap.shutdown()
"""

from __future__ import annotations

from typing import List, Optional

from .config import LoggingConfig
from .container import LoggingContainer
from .diagnostics import LoggingDiagnostics
from .handlers import ConsoleHandler, LogHandler
from .lifecycle import LoggingLifecycle
from .manager import LoggerManager
from .metrics import LoggingMetrics
from .pipeline import LoggingPipeline
from .registry import LoggingRegistry
from .scheduler import LoggingScheduler
from .service import LoggingService
from .telemetry import LoggingTelemetry


class LoggingBootstrap:
    """
    Logging platform bootstrap.

    Orchestrates the initialization of all
    logging components:

    1. Create DI container
    2. Register all components
    3. Wire dependencies
    4. Manage lifecycle

    Features:
    - One-line initialization
    - Configurable handlers
    - Metrics registration
    - Telemetry export
    - Graceful shutdown

    Usage:
        bootstrap = LoggingBootstrap()
        await bootstrap.startup()

        logger = bootstrap.get_logger("strategy")
        logger.info("Hello")

        await bootstrap.shutdown()
    """

    def __init__(
        self,
        config: Optional[LoggingConfig] = None,
        handlers: Optional[List[LogHandler]] = None,
        enable_telemetry: bool = False,
        prometheus: Optional[object] = None,
    ) -> None:
        """
        Initialize bootstrap.

        Args:
            config: Logging configuration.
            handlers: List of log handlers.
            enable_telemetry: Whether to enable telemetry.
            prometheus: Optional Prometheus registry for metrics.
        """

        self._config = config or LoggingConfig()
        self._handlers: List[LogHandler] = handlers or [
            ConsoleHandler(format_type="json")
        ]
        self._enable_telemetry = enable_telemetry
        self._prometheus = prometheus

        # DI Container
        self._container = LoggingContainer()
        self._container.register_defaults(
            config=self._config,
            handlers=self._handlers,
        )

        # Additional components
        self._metrics = self._container.resolve(LoggingMetrics)
        self._manager = self._container.resolve(LoggerManager)
        self._service = self._container.resolve(LoggingService)
        self._pipeline = self._container.resolve(LoggingPipeline)
        self._scheduler = self._container.resolve(LoggingScheduler)
        self._lifecycle = self._container.resolve(LoggingLifecycle)

        # Diagnostics
        self._diagnostics = LoggingDiagnostics(
            pipeline=self._pipeline,
            metrics=self._metrics,
        )

        # Registry (Prometheus)
        self._registry = LoggingRegistry(
            prometheus=self._prometheus,
            metrics=self._metrics,
        )

        # Telemetry
        self._telemetry = LoggingTelemetry(
            metrics=self._metrics,
        ) if enable_telemetry else None

        self._started: bool = False

    @property
    def config(
        self,
    ) -> LoggingConfig:
        """Get logging config."""
        return self._config

    @property
    def manager(
        self,
    ) -> LoggerManager:
        """Get logger manager."""
        return self._manager

    @property
    def service(
        self,
    ) -> LoggingService:
        """Get logging service."""
        return self._service

    @property
    def pipeline(
        self,
    ) -> LoggingPipeline:
        """Get logging pipeline."""
        return self._pipeline

    @property
    def metrics(
        self,
    ) -> LoggingMetrics:
        """Get logging metrics."""
        return self._metrics

    @property
    def container(
        self,
    ) -> LoggingContainer:
        """Get DI container."""
        return self._container

    @property
    def is_started(
        self,
    ) -> bool:
        """Check if bootstrap is started."""
        return self._started

    def add_handler(
        self,
        handler: LogHandler,
    ) -> None:
        """
        Add a log handler.

        Args:
            handler: Handler to add.
        """

        self._handlers.append(handler)
        self._service.add_handler(handler)

    def add_collector(
        self,
        name: str,
        collector: object,
    ) -> None:
        """
        Add a periodic collector to scheduler.

        Args:
            name: Collector name.
            collector: Collector with collect() method.
        """

        self._scheduler.add_task(collector.collect)

    def get_logger(
        self,
        name: str,
    ):
        """
        Get a named logger.

        Args:
            name: Logger name.

        Returns:
            Logger instance.
        """

        return self._manager.get_logger(name)

    async def startup(
        self,
    ) -> None:
        """Start the logging platform."""

        if self._started:
            return

        # Register metrics with Prometheus
        if self._prometheus is not None:
            self._registry.register_metrics()

        # Start lifecycle (starts service + scheduler)
        await self._lifecycle.startup()

        # Start telemetry
        if self._telemetry is not None:
            await self._telemetry.start()

        # Set worker status
        self._registry.set_worker_status(True)

        self._started = True

    async def shutdown(
        self,
    ) -> None:
        """
        Shutdown the logging platform.

        Ensures graceful shutdown:
        1. Stop accepting new logs
        2. Flush remaining queue
        3. Close all handlers
        4. Export final metrics
        """

        if not self._started:
            return

        # Set worker status
        self._registry.set_worker_status(False)

        # Stop telemetry
        if self._telemetry is not None:
            await self._telemetry.stop()

        # Shutdown lifecycle (stops scheduler + service)
        await self._lifecycle.shutdown()

        self._started = False

    async def diagnostics(
        self,
    ) -> dict:
        """
        Get diagnostics snapshot.

        Returns:
            Diagnostics dictionary.
        """

        return await self._diagnostics.snapshot()

    async def health_check(
        self,
    ) -> dict:
        """
        Run health check.

        Returns:
            Health status dictionary.
        """

        return await self._diagnostics.health_check()

    def get_status(
        self,
    ) -> dict:
        """
        Get bootstrap status.

        Returns:
            Status dictionary.
        """

        return {
            "started": self._started,
            "config": self._config.to_dict(),
            "handlers": len(self._handlers),
            "loggers": self._manager.logger_count,
            "metrics": self._metrics.to_dict(),
            "registry": self._registry.get_status(),
            "telemetry": (
                self._telemetry.get_status()
                if self._telemetry
                else None
            ),
            "lifecycle": self._lifecycle.get_status(),
            "scheduler": self._scheduler.get_status(),
        }
