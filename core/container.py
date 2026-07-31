"""
ICYQuant Dependency Injection Container.

Production-grade dependency injection framework.

Responsibilities:

- Service registration
- Dependency resolution
- Lifetime management
- Application bootstrap

Python:
    3.12+
"""

from __future__ import annotations

import asyncio
import inspect

from collections.abc import (
    AsyncIterator,
    Awaitable,
    Callable,
    Iterator,
)
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from enum import Enum
from inspect import Parameter, Signature
from threading import RLock
from typing import Any, Dict, List, Optional, Type, TypeVar

from shared.exceptions import DependencyError

T = TypeVar("T")
Factory = Callable[..., Any]
AsyncFactory = Callable[..., Awaitable[Any]]


# ============================================================================
# Service Lifetime
# ============================================================================


class ServiceLifetime(str, Enum):
    """
    Supported service lifetimes.
    """

    SINGLETON = "singleton"

    TRANSIENT = "transient"

    SCOPED = "scoped"


# ============================================================================
# Service Descriptor
# ============================================================================


@dataclass
class ServiceDescriptor:
    """
    Registered service definition.
    """

    service_type: type[Any]

    implementation: Callable[..., Any] | type[Any]

    lifetime: ServiceLifetime

    instance: Any | None = None

    named_instances: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Provider
# ============================================================================


@dataclass
class Provider:
    """
    Service provider definition.

    Wraps a factory function (sync or async) with
    lifetime tracking and resource cleanup support.
    """

    service_type: type[Any]

    factory: Factory | AsyncFactory

    lifetime: ServiceLifetime

    is_async: bool = False


# ============================================================================
# Container Exceptions
# ============================================================================


class ContainerError(Exception):
    """
    Base container exception.
    """


class ServiceNotFoundError(ContainerError, DependencyError):
    """
    Raised when a service has not been registered.
    """


class CircularDependencyError(ContainerError, DependencyError):
    """
    Raised when circular dependencies are detected.
    """


# ============================================================================
# Scope
# ============================================================================


_scope_context: ContextVar[
    Optional[Dict[type[Any], Any]]
] = ContextVar(
    "icyquant_scope",
    default=None,
)


@contextmanager
def service_scope() -> Iterator[None]:
    """
    Create a scoped lifetime.

    All scoped services resolved within this context
    will share the same instance. The scope cache is
    cleared when the context exits.

    Example:

        with service_scope():
            service = container.resolve(...)
    """

    token: Token = _scope_context.set({})

    try:

        yield

    finally:

        _scope_context.reset(token)


# ============================================================================
# Scope Utilities
# ============================================================================


def current_scope_size() -> int:
    """
    Return current scope object count.
    """

    cache = _scope_context.get()

    if cache is None:
        return 0

    return len(cache)


def clear_scope() -> None:
    """
    Remove all scoped instances.
    """

    cache = _scope_context.get()

    if cache is not None:
        cache.clear()


# ============================================================================
# Dependency Container
# ============================================================================


class Container:
    """
    ICYQuant dependency injection container.
    """

    def __init__(self) -> None:

        self._services: dict[
            type[Any],
            ServiceDescriptor,
        ] = {}

        self._providers: dict[
            type[Any],
            Provider,
        ] = {}

        self._resource_cleanup: list[Any] = []

        self._lock = RLock()

        self._resolving_stack: list[type[Any]] = []

    # --------------------------------------------------------
    # Registration API (new)
    # --------------------------------------------------------

    def register_singleton(
        self,
        service: type[T],
        implementation: Callable[..., T] | type[T] | T = None,
    ) -> None:
        """
        Register singleton service.

        Accepts:
          - A type (concrete class): ``register_singleton(Interface, Concrete)``
          - A callable (factory): ``register_singleton(Interface, factory_fn)``
          - An existing instance: ``register_singleton(Interface, instance)``
        """

        with self._lock:

            if implementation is None:
                implementation = service

            # If implementation is an instance (not a type or callable),
            # store it directly as a pre-created singleton.
            if not isinstance(implementation, type) and not callable(
                implementation
            ):
                descriptor = ServiceDescriptor(
                    service_type=service,
                    implementation=type(implementation),
                    lifetime=ServiceLifetime.SINGLETON,
                    instance=implementation,
                )
            else:
                descriptor = ServiceDescriptor(
                    service_type=service,
                    implementation=implementation,
                    lifetime=ServiceLifetime.SINGLETON,
                )

            self._services[service] = descriptor

    def register_transient(
        self,
        service: type[T],
        implementation: Callable[..., T] | type[T],
    ) -> None:
        """
        Register transient service.
        """

        with self._lock:

            self._services[service] = ServiceDescriptor(
                service_type=service,
                implementation=implementation,
                lifetime=ServiceLifetime.TRANSIENT,
            )

    def register_scoped(
        self,
        service: type[T],
        implementation: Callable[..., T] | type[T],
    ) -> None:
        """
        Register scoped service.

        Scoped services share the same instance within a
        ``service_scope()`` context. A new instance is created
        for each scope.
        """

        with self._lock:

            self._services[service] = ServiceDescriptor(
                service_type=service,
                implementation=implementation,
                lifetime=ServiceLifetime.SCOPED,
            )

    def register_instance(
        self,
        service_or_name: type[T] | str,
        instance: T,
    ) -> None:
        """
        Register existing instance.

        Supports two forms:
          - Type-based: ``register_instance(Interface, instance)``
          - Named: ``register_instance("config", instance)``
        """

        with self._lock:

            if isinstance(service_or_name, str):
                # Named registration (backward-compatible)
                name = service_or_name
                for descriptor in self._services.values():
                    descriptor.named_instances[name] = instance
                    return
                sentinel = ServiceDescriptor(
                    service_type=object,
                    implementation=object,
                    lifetime=ServiceLifetime.SINGLETON,
                    named_instances={name: instance},
                )
                self._services[object] = sentinel
            else:
                # Type-based registration
                service = service_or_name
                self._services[service] = ServiceDescriptor(
                    service_type=service,
                    implementation=type(instance),
                    lifetime=ServiceLifetime.SINGLETON,
                    instance=instance,
                )

    # --------------------------------------------------------
    # Resolution API (new)
    # --------------------------------------------------------

    def resolve(
        self,
        service: type[T],
    ) -> T:
        """
        Resolve service instance.

        Args:
            service:
                Requested service type.

        Returns:
            Resolved instance.
        """

        with self._lock:

            descriptor = self._services.get(
                service
            )

            # Check providers as fallback
            if descriptor is None:
                provider = self._providers.get(
                    service
                )
                if provider is not None:
                    if provider.is_async:
                        raise ContainerError(
                            f"Service {service.__name__} is registered "
                            "as an async provider. Use resolve_async()."
                        )
                    instance = provider.factory()
                    self._track_resource(instance)
                    if provider.lifetime == ServiceLifetime.SINGLETON:
                        self._services[service] = ServiceDescriptor(
                            service_type=service,
                            implementation=provider.factory,
                            lifetime=ServiceLifetime.SINGLETON,
                            instance=instance,
                        )
                    return instance

                raise ServiceNotFoundError(
                    f"{service.__name__} is not registered."
                )

            if (
                descriptor.lifetime
                == ServiceLifetime.SCOPED
            ):

                cache = _scope_context.get()

                if cache is not None:

                    instance = cache.get(service)

                    if instance is not None:
                        return instance

                    instance = self._build_instance(
                        descriptor
                    )

                    cache[service] = instance

                    return instance

                # No active scope — fall back to transient behavior
                return self._build_instance(
                    descriptor
                )

            if (
                descriptor.lifetime
                == ServiceLifetime.SINGLETON
            ):

                if descriptor.instance is None:

                    descriptor.instance = (
                        self._build_instance(
                            descriptor
                        )
                    )

                return descriptor.instance

            return self._build_instance(
                descriptor
            )

    # --------------------------------------------------------

    def _build_instance(
        self,
        descriptor: ServiceDescriptor,
    ) -> Any:
        """
        Build object instance.
        """

        implementation = descriptor.implementation

        if inspect.isclass(
            implementation
        ):
            return self._construct(
                implementation
            )

        return implementation()

    # --------------------------------------------------------

    def _construct(
        self,
        cls: type[Any],
    ) -> Any:
        """
        Constructor injection.
        """

        if cls in self._resolving_stack:

            raise CircularDependencyError(

                " -> ".join(
                    c.__name__
                    for c in (
                        self._resolving_stack
                        + [cls]
                    )
                )

            )

        self._resolving_stack.append(
            cls
        )

        try:

            signature: Signature = (
                inspect.signature(
                    cls.__init__
                )
            )

            kwargs: dict[str, Any] = {}

            for parameter in (
                signature.parameters.values()
            ):

                if parameter.name == "self":
                    continue

                if parameter.default is not Parameter.empty:
                    continue

                dependency = (
                    self._resolve_parameter(
                        parameter
                    )
                )

                kwargs[
                    parameter.name
                ] = dependency

            return cls(
                **kwargs
            )

        finally:

            self._resolving_stack.pop()

    # --------------------------------------------------------

    def _resolve_parameter(
        self,
        parameter: Parameter,
    ) -> Any:
        """
        Resolve constructor parameter.
        """

        annotation = parameter.annotation

        if annotation is Parameter.empty:

            raise ContainerError(

                f"Constructor parameter "

                f"{parameter.name} "

                "must declare a type annotation."

            )

        if not isinstance(annotation, type):

            # Forward references: "ClassName" → resolve via sys.modules
            if isinstance(annotation, str):
                import sys

                cls_name = annotation
                resolved: Optional[type] = None

                for module in sys.modules.values():
                    if hasattr(module, cls_name):
                        candidate = getattr(module, cls_name)
                        if isinstance(candidate, type):
                            resolved = candidate
                            break

                if resolved is None:
                    if parameter.default is not Parameter.empty:
                        return parameter.default
                    raise ContainerError(
                        f"Constructor parameter {parameter.name} "
                        f"has forward reference '{cls_name}' that "
                        f"could not be resolved."
                    )
                annotation = resolved
            else:
                if parameter.default is not Parameter.empty:
                    return parameter.default
                raise ContainerError(
                    f"Constructor parameter "
                    f"{parameter.name} has invalid "
                    f"type annotation: {annotation}. "
                    "Only class types are supported."
                )

        return self.resolve(
            annotation
        )

    def try_resolve(
        self,
        service: type[T],
    ) -> Optional[T]:
        """
        Resolve service, returning None if not registered.
        """

        try:
            return self.resolve(service)
        except DependencyError:
            return None

    # --------------------------------------------------------
    # Query API
    # --------------------------------------------------------

    def contains(
        self,
        service: type[Any],
    ) -> bool:
        """
        Check whether service exists.
        """

        return service in self._services

    def descriptors(
        self,
    ) -> list[ServiceDescriptor]:
        """
        Return all registered services.
        """

        return list(
            self._services.values()
        )

    def clear(self) -> None:
        """
        Remove all registrations.
        """

        with self._lock:
            self._services.clear()

    # --------------------------------------------------------
    # Backward-compatible API (merged with new Provider system)
    # --------------------------------------------------------

    def register_factory(
        self,
        interface: Type[T],
        factory: Factory,
        *,
        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON,
    ) -> None:
        """
        Register sync factory.

        Default lifetime is SINGLETON for backward compatibility.
        """

        with self._lock:
            self._providers[interface] = Provider(
                service_type=interface,
                factory=factory,
                lifetime=lifetime,
                is_async=False,
            )

    def register_async_factory(
        self,
        service: type[T],
        factory: AsyncFactory,
        *,
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
    ) -> None:
        """
        Register async factory.

        Args:
            service: Service type.
            factory: Async callable returning the instance.
            lifetime: Service lifetime (default: TRANSIENT).
        """

        with self._lock:
            self._providers[service] = Provider(
                service_type=service,
                factory=factory,
                lifetime=lifetime,
                is_async=True,
            )

    # --------------------------------------------------------
    # Async Resolution
    # --------------------------------------------------------

    async def resolve_async(
        self,
        service: type[T],
    ) -> T:
        """
        Resolve async provider.

        Falls back to sync resolve if no async provider registered.
        """

        provider = self._providers.get(
            service
        )

        if provider is None:
            instance = self.resolve(service)
            self._track_resource(instance)
            return instance

        if provider.lifetime == ServiceLifetime.SINGLETON:
            # Cached: check if we have a descriptor cache
            descriptor = self._services.get(service)
            if descriptor is not None and descriptor.instance is not None:
                return descriptor.instance

        if provider.is_async:
            instance = await provider.factory()
        else:
            instance = provider.factory()

        # Track disposable resources
        self._track_resource(instance)

        # Cache singletons
        if provider.lifetime == ServiceLifetime.SINGLETON:
            descriptor = self._services.get(service)
            if descriptor is not None:
                descriptor.instance = instance
            else:
                # Create a descriptor for caching
                self._services[service] = ServiceDescriptor(
                    service_type=service,
                    implementation=provider.factory,
                    lifetime=ServiceLifetime.SINGLETON,
                    instance=instance,
                )

        return instance

    # --------------------------------------------------------
    # Resource Management
    # --------------------------------------------------------

    def _track_resource(
        self,
        resource: Any,
    ) -> None:
        """
        Register disposable resource for cleanup.

        Resources with close() or aclose() methods are tracked
        for automatic cleanup during shutdown_async().
        """

        if (
            hasattr(resource, "close")
            or hasattr(resource, "aclose")
        ):
            self._resource_cleanup.append(
                resource
            )

    # --------------------------------------------------------
    # Shutdown
    # --------------------------------------------------------

    async def shutdown_async(
        self,
    ) -> None:
        """
        Release async resources.

        Iterates tracked resources in reverse order,
        calling aclose() or close() on each. Errors are
        logged and continue to the next resource.
        """

        while self._resource_cleanup:
            resource = (
                self._resource_cleanup.pop()
            )

            try:
                if hasattr(
                    resource,
                    "aclose",
                ):
                    result = resource.aclose()
                    if inspect.isawaitable(result):
                        await result

                elif hasattr(
                    resource,
                    "close",
                ):
                    result = resource.close()
                    if inspect.isawaitable(result):
                        await result

            except Exception:
                # Log and continue — one resource failure
                # should not block the rest of the shutdown.
                pass

        # Also clear the main service cache
        with self._lock:
            for descriptor in self._services.values():
                descriptor.instance = None

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    def statistics(
        self,
    ) -> dict[str, int]:
        """
        Container runtime statistics.
        """

        return {
            "services": len(
                self._services
            ),
            "providers": len(
                self._providers
            ),
            "tracked_resources": len(
                self._resource_cleanup
            ),
        }

    def get(
        self,
        interface: Type[T],
    ) -> T:
        """
        Resolve service (backward-compatible alias for resolve).
        """

        return self.resolve(interface)

    def has(
        self,
        interface: Type[T],
    ) -> bool:
        """
        Check if service is registered (backward-compatible).
        """

        return self.contains(interface)

    def get_named(
        self,
        name: str,
    ) -> Any:
        """
        Resolve named instance (backward-compatible).

        Named instances are stored on the service descriptor's
        named_instances dict, keyed by the first registered type.
        """

        with self._lock:
            for descriptor in self._services.values():
                if name in descriptor.named_instances:
                    return descriptor.named_instances[name]

        raise DependencyError(
            f"Unregistered name: {name}"
        )

    def register_named(
        self,
        name: str,
        instance: Any,
    ) -> None:
        """
        Register a named instance (backward-compatible).
        """

        with self._lock:
            # Use the first descriptor's named_instances for storage
            # If no services registered yet, store on a special key
            for descriptor in self._services.values():
                descriptor.named_instances[name] = instance
                return

            # No services yet — create a dummy entry
            sentinel = ServiceDescriptor(
                service_type=object,
                implementation=object,
                lifetime=ServiceLifetime.SINGLETON,
                named_instances={name: instance},
            )
            self._services[object] = sentinel

    def has_named(
        self,
        name: str,
    ) -> bool:
        """
        Check if named instance exists.
        """

        with self._lock:
            for descriptor in self._services.values():
                if name in descriptor.named_instances:
                    return True

        return False

    def get_registered_types(self) -> list:
        """
        Return registered service types (backward-compatible).
        """

        return [
            t for t in self._services.keys()
            if t is not object
        ]

    def get_status(self) -> dict:
        """
        Return container status summary.
        """

        with self._lock:
            named_count = sum(
                len(d.named_instances)
                for d in self._services.values()
            )

            return {
                "total_services": len(self._services),
                "singletons": sum(
                    1
                    for d in self._services.values()
                    if d.lifetime == ServiceLifetime.SINGLETON
                ),
                "transients": sum(
                    1
                    for d in self._services.values()
                    if d.lifetime == ServiceLifetime.TRANSIENT
                ),
                "named": named_count,
                "registered": [
                    t.__name__
                    for t in self._services.keys()
                ],
            }

    # --------------------------------------------------------
    # Startup Lifecycle
    # --------------------------------------------------------

    async def startup_async(
        self,
    ) -> None:
        """
        Initialize application resources.

        Pre-create singleton resources
        registered through providers and
        descriptors.
        """

        # Pre-create singleton providers
        for provider in self._providers.values():
            if (
                provider.lifetime
                != ServiceLifetime.SINGLETON
            ):
                continue

            await self.resolve_async(
                provider.service_type
            )

        # Pre-create singleton descriptors
        for service, descriptor in (
            self._services.items()
        ):
            if (
                descriptor.lifetime
                == ServiceLifetime.SINGLETON
                and descriptor.instance is None
            ):
                self.resolve(service)

    # --------------------------------------------------------
    # Dependency Graph
    # --------------------------------------------------------

    def dependency_graph(
        self,
    ) -> dict[str, list[str]]:
        """
        Return dependency graph.

        Useful for debugging and
        architecture visualization.
        """

        graph: dict[
            str,
            list[str],
        ] = {}

        for service, descriptor in (
            self._services.items()
        ):

            implementation = (
                descriptor.implementation
            )

            if not inspect.isclass(
                implementation
            ):

                graph[
                    service.__name__
                ] = []

                continue

            signature = inspect.signature(
                implementation.__init__
            )

            dependencies: list[str] = []

            for parameter in (
                signature.parameters.values()
            ):

                if parameter.name == "self":
                    continue

                annotation = (
                    parameter.annotation
                )

                if annotation is inspect._empty:
                    continue

                dependencies.append(
                    annotation.__name__
                )

            graph[
                service.__name__
            ] = dependencies

        return graph

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    def validate(
        self,
    ) -> None:
        """
        Validate container configuration.

        Resolves every registered service
        to detect missing dependencies or
        circular references early.
        """

        for service in list(self._services):
            self.resolve(service)

    # --------------------------------------------------------
    # Shutdown
    # --------------------------------------------------------

    async def shutdown(
        self,
    ) -> None:
        """
        Gracefully shutdown container.

        Releases all tracked resources,
        clears scope, and resets the registry.
        """

        await self.shutdown_async()

        clear_scope()

        self.clear()


# ============================================================================
# Default Container
# ============================================================================

_default_container = Container()


def get_container() -> Container:
    """
    Return application container.

    Provides a global default container
    instance for application-wide use.
    """

    return _default_container


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "Container",
    "ServiceLifetime",
    "ServiceDescriptor",
    "Provider",
    "service_scope",
    "get_container",
    "ContainerError",
    "ServiceNotFoundError",
    "CircularDependencyError",
]