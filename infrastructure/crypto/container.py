"""
Dependency injection container for the crypto platform.

Provides a lightweight DI container for registering
and resolving cryptographic platform components.

Supports:
- Singleton registration
- Factory registration
- Instance registration
- Interface-to-implementation binding
"""

from __future__ import annotations

import inspect
import threading
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

T = TypeVar("T")


class CryptoContainer:
    """
    Lightweight dependency injection container for crypto.

    Manages singleton instances of cryptographic
    platform components and their dependencies.

    Usage:
        container = CryptoContainer()

        # Register singletons
        container.register_singleton(CryptoService)
        container.register_singleton(CryptoManager)
        container.register_singleton(KeyStore)

        # Register with factory
        container.register_factory(Keyring, create_keyring)

        # Resolve
        service = container.resolve(CryptoService)
    """

    def __init__(
        self,
    ) -> None:
        """Initialize crypto DI container."""
        self._singletons: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable] = {}
        self._instances: Dict[Type, Any] = {}
        self._bindings: Dict[Type, Type] = {}
        self._lock = threading.RLock()

    def register_singleton(
        self,
        cls: Type[T],
        factory: Optional[Callable] = None,
    ) -> None:
        """
        Register a class as a singleton.

        Args:
            cls: Class to register.
            factory: Optional factory function.
        """
        with self._lock:
            if factory:
                self._factories[cls] = factory
            else:
                self._singletons[cls] = cls

    def register_factory(
        self,
        cls: Type[T],
        factory: Callable,
    ) -> None:
        """
        Register a factory for a type.

        Args:
            cls: Type to register.
            factory: Factory callable.
        """
        with self._lock:
            self._factories[cls] = factory

    def register_instance(
        self,
        cls: Type[T],
        instance: T,
    ) -> None:
        """
        Register a pre-built instance.

        Args:
            cls: Type to register.
            instance: Pre-built instance.
        """
        with self._lock:
            self._instances[cls] = instance

    def bind(
        self,
        interface: Type[T],
        implementation: Type[T],
    ) -> None:
        """
        Bind an interface to an implementation.

        Args:
            interface: Abstract type.
            implementation: Concrete type.
        """
        with self._lock:
            self._bindings[interface] = implementation

    def resolve(
        self,
        cls: Type[T],
    ) -> Optional[T]:
        """
        Resolve a registered type.

        Args:
            cls: Type to resolve.

        Returns:
            Instance or None.
        """
        with self._lock:
            if cls in self._instances:
                return self._instances[cls]

            actual_cls = self._bindings.get(cls, cls)

            if actual_cls in self._instances:
                return self._instances[actual_cls]

            if actual_cls in self._factories:
                instance = self._factories[actual_cls]()
                self._instances[actual_cls] = instance
                return instance

            if actual_cls in self._singletons:
                factory = self._singletons[actual_cls]
                if callable(factory) and not isinstance(factory, type):
                    instance = factory()
                else:
                    instance = self._create_instance(actual_cls)
                self._instances[actual_cls] = instance
                return instance

            return None

    def _create_instance(
        self,
        cls: Type[T],
    ) -> T:
        """
        Create an instance, resolving constructor dependencies.

        Args:
            cls: Class to instantiate.

        Returns:
            Instance.
        """
        try:
            sig = inspect.signature(cls.__init__)
            kwargs = {}

            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue
                if param.annotation != inspect.Parameter.empty:
                    dep = self.resolve(param.annotation)
                    if dep is not None:
                        kwargs[param_name] = dep
                elif param.default != inspect.Parameter.empty:
                    continue

            return cls(**kwargs)
        except Exception:
            try:
                return cls()
            except Exception:
                return None

    def is_registered(
        self,
        cls: Type,
    ) -> bool:
        """Check if a type is registered."""
        with self._lock:
            return (
                cls in self._singletons
                or cls in self._factories
                or cls in self._instances
                or cls in self._bindings
            )

    def list_registrations(
        self,
    ) -> List[str]:
        """List all registered type names."""
        with self._lock:
            types = set()
            types.update(self._singletons.keys())
            types.update(self._factories.keys())
            types.update(self._instances.keys())
            types.update(self._bindings.keys())
            return sorted([t.__name__ for t in types])

    def clear(
        self,
    ) -> None:
        """Clear all registrations."""
        with self._lock:
            self._singletons.clear()
            self._factories.clear()
            self._instances.clear()
            self._bindings.clear()


def create_default_container() -> CryptoContainer:
    """
    Create a crypto DI container with default registrations.

    Returns:
        Configured CryptoContainer.
    """
    container = CryptoContainer()

    from .service import CryptoService
    from .manager import CryptoManager
    from .keystore import KeyStore
    from .keyring import Keyring
    from .registry import AlgorithmRegistry

    container.register_singleton(CryptoService)
    container.register_singleton(CryptoManager)
    container.register_singleton(KeyStore)
    container.register_singleton(Keyring)
    container.register_singleton(AlgorithmRegistry)

    return container