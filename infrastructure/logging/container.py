"""
Logging dependency injection container.

Provides a lightweight DI container for
registering and resolving logging components,
enabling clean separation of configuration
and component wiring.

Usage:
    container = LoggingContainer()
    container.register_defaults(config)
    service = container.resolve(LoggingService)
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Type

from .config import LoggingConfig
from .manager import LoggerManager
from .service import LoggingService
from .scheduler import LoggingScheduler
from .lifecycle import LoggingLifecycle
from .metrics import LoggingMetrics
from .pipeline import LoggingPipeline
from .queue import LogQueue
from .batch import BatchCollector
from .dispatcher import LogDispatcher
from .worker import LoggingWorker
from .handlers import ConsoleHandler, LogHandler, NullHandler


class LoggingContainer:
    """
    Lightweight dependency injection container.

    Manages singleton instances of logging
    components, ensuring proper wiring and
    lifecycle management.

    Features:
    - Singleton registration
    - Factory registration
    - Auto-wiring of dependencies
    - Instance resolution

    Usage:
        container = LoggingContainer()
        container.register_defaults()
        service = container.resolve(LoggingService)
    """

    def __init__(
        self,
    ) -> None:
        """Initialize container."""

        self._instances: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable] = {}

    def register_singleton(
        self,
        interface: Type,
        instance: Any,
    ) -> None:
        """
        Register a singleton instance.

        Args:
            interface: Type key for resolution.
            instance: Singleton instance.
        """

        self._instances[interface] = instance

    def register_factory(
        self,
        interface: Type,
        factory: Callable,
    ) -> None:
        """
        Register a factory function.

        Args:
            interface: Type key for resolution.
            factory: Callable that creates instances.
        """

        self._factories[interface] = factory

    def resolve(
        self,
        interface: Type,
    ) -> Any:
        """
        Resolve an instance.

        Args:
            interface: Type to resolve.

        Returns:
            Instance of the requested type.

        Raises:
            KeyError: If type is not registered.
        """

        if interface in self._instances:
            return self._instances[interface]

        if interface in self._factories:
            instance = self._factories[interface]()
            self._instances[interface] = instance
            return instance

        raise KeyError(
            f"Type {interface} not registered in container"
        )

    def is_registered(
        self,
        interface: Type,
    ) -> bool:
        """Check if a type is registered."""

        return (
            interface in self._instances
            or interface in self._factories
        )

    def clear(
        self,
    ) -> None:
        """Clear all registrations."""

        self._instances.clear()
        self._factories.clear()

    def register_defaults(
        self,
        config: Optional[LoggingConfig] = None,
        handlers: Optional[list] = None,
    ) -> None:
        """
        Register default logging components.

        Creates and wires all standard logging
        components with sensible defaults.

        Args:
            config: Logging configuration.
            handlers: List of log handlers.
        """

        config = config or LoggingConfig()
        handlers = handlers or [ConsoleHandler()]

        # Metrics
        metrics = LoggingMetrics()
        self.register_singleton(LoggingMetrics, metrics)

        # Logger manager
        manager = LoggerManager(config=config)
        for handler in handlers:
            manager.add_handler(handler)
        self.register_singleton(LoggerManager, manager)

        # Pipeline
        pipeline = LoggingPipeline(
            handlers=handlers,
            queue_size=10000,
            batch_size=100,
            flush_interval=1.0,
        )
        self.register_singleton(LoggingPipeline, pipeline)

        # Service
        service = LoggingService(
            config=config,
            handlers=handlers,
        )
        self.register_singleton(LoggingService, service)

        # Scheduler
        scheduler = LoggingScheduler(
            metrics=metrics,
            pipeline=pipeline,
            interval=5.0,
        )
        self.register_singleton(LoggingScheduler, scheduler)

        # Lifecycle
        async def _startup():
            await service.startup()
            await scheduler.start()

        async def _shutdown():
            await scheduler.stop()
            await service.shutdown()

        lifecycle = LoggingLifecycle(
            on_startup=_startup,
            on_shutdown=_shutdown,
        )
        self.register_singleton(LoggingLifecycle, lifecycle)


def register_logging(
    container: Any,
    config: Optional[LoggingConfig] = None,
) -> LoggingContainer:
    """
    Register logging components in a DI container.

    Args:
        container: Existing container (or None to create new).
        config: Logging configuration.

    Returns:
        LoggingContainer with all components registered.
    """

    if container is None or not isinstance(container, LoggingContainer):
        container = LoggingContainer()

    container.register_defaults(config=config)
    return container
