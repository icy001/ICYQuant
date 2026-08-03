"""
Monitoring dependency injection container.

Provides registration helpers for wiring
monitoring components into a dependency
injection container.

This module provides a lightweight DI
container implementation that can be used
to register and resolve monitoring
components. It can also be used alongside
external DI frameworks by using the
register_all() method as a reference.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Type


class DIContainer:
    """
    Lightweight dependency injection container.

    Supports singleton and factory registrations
    for monitoring components.

    Usage:
        container = DIContainer()

        container.register_singleton(
            MonitoringService,
            factory=lambda: service
        )

        service = container.resolve(MonitoringService)
    """

    def __init__(
        self,
    ) -> None:
        """Initialize empty container."""

        self._singletons: Dict[type, Any] = {}
        self._factories: Dict[type, Callable] = {}
        self._instances: Dict[type, Any] = {}

    def register_singleton(
        self,
        interface: type,
        factory: Optional[Callable] = None,
        instance: Optional[Any] = None,
    ) -> None:
        """
        Register a singleton.

        Args:
            interface: Type to register.
            factory: Optional factory callable.
            instance: Optional pre-created instance.
        """

        if instance is not None:
            self._singletons[interface] = instance
        elif factory is not None:
            self._factories[interface] = factory
        else:
            self._factories[interface] = interface

    def register_factory(
        self,
        interface: type,
        factory: Callable,
    ) -> None:
        """
        Register a factory (new instance each resolve).

        Args:
            interface: Type to register.
            factory: Factory callable.
        """

        self._factories[interface] = factory

    def resolve(
        self,
        interface: type,
    ) -> Any:
        """
        Resolve a registered type.

        Args:
            interface: Type to resolve.

        Returns:
            Resolved instance.

        Raises:
            KeyError: If type not registered.
        """

        if interface in self._singletons:
            return self._singletons[interface]

        if interface in self._instances:
            return self._instances[interface]

        if interface in self._factories:
            factory = self._factories[interface]
            instance = factory()

            if interface in self._singletons:
                self._instances[interface] = instance

            return instance

        raise KeyError(
            f"Type not registered: {interface}"
        )

    def is_registered(
        self,
        interface: type,
    ) -> bool:
        """
        Check if a type is registered.

        Args:
            interface: Type to check.

        Returns:
            True if registered.
        """

        return (
            interface in self._singletons
            or interface in self._factories
        )

    def clear(
        self,
    ) -> None:
        """Clear all registrations."""

        self._singletons.clear()
        self._factories.clear()
        self._instances.clear()


def register_monitoring(
    container: DIContainer,
    bootstrap: Any,
) -> None:
    """
    Register all monitoring components in DI container.

    Args:
        container: DI container instance.
        bootstrap: MonitoringBootstrap instance.
    """

    from .bootstrap import MonitoringBootstrap
    from .config import MonitoringConfig
    from .prometheus import PrometheusRegistry
    from .registry import MetricsRegistry
    from .collector import CollectorRunner
    from .exporter import PrometheusExporter
    from .service import MonitoringService
    from .scheduler import MonitoringScheduler
    from .telemetry import TelemetryService
    from .tracing import MonitoringTracing
    from .lifecycle import MonitoringLifecycle

    container.register_singleton(
        MonitoringConfig,
        instance=bootstrap.config,
    )
    container.register_singleton(
        PrometheusRegistry,
        instance=bootstrap.prometheus,
    )
    container.register_singleton(
        MetricsRegistry,
        instance=bootstrap.registry,
    )
    container.register_singleton(
        CollectorRunner,
        instance=bootstrap.collector,
    )
    container.register_singleton(
        PrometheusExporter,
        instance=bootstrap.exporter,
    )
    container.register_singleton(
        MonitoringService,
        instance=bootstrap.service,
    )
    container.register_singleton(
        MonitoringScheduler,
        instance=bootstrap.scheduler,
    )
    container.register_singleton(
        TelemetryService,
        instance=bootstrap.telemetry,
    )
    container.register_singleton(
        MonitoringTracing,
        instance=bootstrap.tracing,
    )
    container.register_singleton(
        MonitoringLifecycle,
        instance=bootstrap.lifecycle,
    )
    container.register_singleton(
        MonitoringBootstrap,
        instance=bootstrap,
    )
