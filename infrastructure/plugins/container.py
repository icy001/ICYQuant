from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Type

from .exceptions import PluginError

logger = logging.getLogger(__name__)


class Container:
    """Thread-safe dependency injection container.

    Supports singleton, transient, and factory lifetimes for
    managing service instances across the plugin framework.

    Usage::

        container = Container()
        container.register_singleton(PluginRegistry, PluginRegistry())
        container.register_transient(PluginLoader, lambda: PluginLoader())
        registry = container.resolve(PluginRegistry)
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._singletons: Dict[Type, Any] = {}
        self._transients: Dict[Type, Callable[[], Any]] = {}
        self._factories: Dict[Type, Callable[..., Any]] = {}

    def register_singleton(self, cls: Type, instance: Any = None) -> None:
        """Register a singleton instance.

        Args:
            cls: The type to register the instance under.
            instance: The singleton instance to return on resolution.
        """
        with self._lock:
            self._singletons[cls] = instance
            self._transients.pop(cls, None)
            self._factories.pop(cls, None)
            logger.debug("Registered singleton for '%s'.", cls.__name__)

    def register_transient(self, cls: Type, factory: Callable[[], Any]) -> None:
        """Register a transient factory (new instance per resolution).

        Args:
            cls: The type to register the factory under.
            factory: A callable that returns a new instance.
        """
        with self._lock:
            self._transients[cls] = factory
            self._singletons.pop(cls, None)
            self._factories.pop(cls, None)
            logger.debug("Registered transient for '%s'.", cls.__name__)

    def register_factory(self, cls: Type, factory: Callable[..., Any]) -> None:
        """Register a factory for advanced creation logic.

        Args:
            cls: The type to register the factory under.
            factory: A callable that creates and returns an instance.
        """
        with self._lock:
            self._factories[cls] = factory
            self._singletons.pop(cls, None)
            self._transients.pop(cls, None)
            logger.debug("Registered factory for '%s'.", cls.__name__)

    def resolve(self, cls: Type) -> Any:
        """Resolve an instance by type.

        Resolution order: singleton → transient → factory.

        Args:
            cls: The type to resolve.

        Returns:
            The resolved instance.

        Raises:
            PluginError: If the type is not registered.
        """
        with self._lock:
            if cls in self._singletons:
                return self._singletons[cls]

            if cls in self._transients:
                factory = self._transients[cls]
                return factory()

            if cls in self._factories:
                factory = self._factories[cls]
                return factory()

        raise PluginError(
            f"No registration found for type '{cls.__name__}'. "
            f"Register it before resolving."
        )

    def has(self, cls: Type) -> bool:
        """Check if a type is registered.

        Args:
            cls: The type to check.

        Returns:
            True if the type is registered.
        """
        with self._lock:
            return (
                cls in self._singletons
                or cls in self._transients
                or cls in self._factories
            )

    def clear(self) -> None:
        """Clear all registrations."""
        with self._lock:
            self._singletons.clear()
            self._transients.clear()
            self._factories.clear()
            logger.info("Container cleared.")

    def get_registered_types(self) -> List[str]:
        """List all registered type names.

        Returns:
            A list of fully-qualified type names.
        """
        with self._lock:
            types: set[str] = set()
            for cls in self._singletons:
                types.add(cls.__name__)
            for cls in self._transients:
                types.add(cls.__name__)
            for cls in self._factories:
                types.add(cls.__name__)
            return sorted(types)

    def get_stats(self) -> Dict[str, Any]:
        """Get container statistics.

        Returns:
            A dictionary with registration counts and type info.
        """
        with self._lock:
            return {
                "singletons": len(self._singletons),
                "transients": len(self._transients),
                "factories": len(self._factories),
                "registered_types": self.get_registered_types(),
            }