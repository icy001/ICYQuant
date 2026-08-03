"""
Tracing dependency injection container.

Provides registration helpers for wiring
tracing components into a dependency
injection container.

This module provides a lightweight DI
container implementation that can be used
to register and resolve tracing
components. It can also be used alongside
external DI frameworks by using the
register_all() method as a reference.

Registrations:
    - TracingConfig
    - TraceRegistry
    - ICYTracerProvider
    - Sampler
    - ExportManager
    - InstrumentationManager
    - TracingService
    - TracingMonitoring
    - TracingScheduler
    - TracingTelemetry
    - TracingLifecycle
    - TracingBootstrap

Usage:
    container = DIContainer()
    register_tracing(container, bootstrap)

    service = container.resolve(TracingService)
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional


class DIContainer:
    """
    Lightweight dependency injection container.

    Supports singleton and factory registrations
    for tracing components.

    Usage:
        container = DIContainer()

        container.register_singleton(
            TracingService,
            factory=lambda: service,
        )

        service = container.resolve(TracingService)
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


def register_tracing(
    container: DIContainer,
    bootstrap: Any,
) -> None:
    """
    Register all tracing components in DI container.

    Args:
        container: DI container instance.
        bootstrap: TracingBootstrap instance.
    """

    from .bootstrap import TracingBootstrap
    from .config import TracingConfig
    from .exporters import ExportManager
    from .instrumentation import InstrumentationManager
    from .lifecycle import TracingLifecycle
    from .monitoring import TracingMonitoring
    from .provider import ICYTracerProvider
    from .registry import TraceRegistry
    from .sampler import Sampler
    from .scheduler import TracingScheduler
    from .service import TracingService
    from .telemetry import TracingTelemetry

    container.register_singleton(
        TracingConfig,
        instance=bootstrap.config,
    )
    container.register_singleton(
        TraceRegistry,
        instance=bootstrap.registry,
    )
    container.register_singleton(
        ICYTracerProvider,
        instance=bootstrap.provider,
    )
    container.register_singleton(
        Sampler,
        instance=bootstrap.sampler,
    )
    container.register_singleton(
        ExportManager,
        instance=bootstrap.export_manager,
    )
    container.register_singleton(
        InstrumentationManager,
        instance=bootstrap.instrumentation_manager,
    )
    container.register_singleton(
        TracingService,
        instance=bootstrap.service,
    )
    container.register_singleton(
        TracingMonitoring,
        instance=bootstrap.monitoring,
    )
    container.register_singleton(
        TracingScheduler,
        instance=bootstrap.scheduler,
    )
    container.register_singleton(
        TracingTelemetry,
        instance=bootstrap.telemetry,
    )
    container.register_singleton(
        TracingLifecycle,
        instance=bootstrap.lifecycle,
    )
    container.register_singleton(
        TracingBootstrap,
        instance=bootstrap,
    )
