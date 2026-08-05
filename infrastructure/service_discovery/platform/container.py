"""Dependency injection container for ICYQuant service discovery.

Provides ``DiscoveryContainer`` for registering and resolving
singleton and transient service instances.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, Optional, Type

logger = logging.getLogger(__name__)


class DiscoveryContainer:
    """Simple dependency injection container.

    Supports singleton registration with lazy resolution,
    factory functions, and automatic resolution by type.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._type_map: Dict[Type, str] = {}
        self._resolution_count = 0
        self._registration_count = 0

    def register_singleton(
        self,
        instance: Any,
        name: Optional[str] = None,
    ) -> str:
        """Register an already-instantiated singleton.

        Args:
            instance: The instance to register.
            name: Optional name; defaults to the class name.

        Returns:
            The registration name.
        """
        cls_name = name or type(instance).__name__
        with self._lock:
            self._singletons[cls_name] = instance
            self._type_map[type(instance)] = cls_name
            self._registration_count += 1
        logger.debug(
            "Registered singleton '%s' (%s).",
            cls_name,
            type(instance).__name__,
        )
        return cls_name

    def register_factory(
        self,
        factory: Callable,
        name: str,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """Register a factory function for lazy instantiation.

        Args:
            factory: Callable that returns the instance.
            name: Registration name.
            *args: Positional args for the factory.
            **kwargs: Keyword args for the factory.

        Returns:
            The registration name.
        """
        with self._lock:
            self._factories[name] = (factory, args, kwargs)
            self._registration_count += 1
        logger.debug("Registered factory '%s'.", name)
        return name

    def resolve(self, name: str) -> Any:
        """Resolve a registered instance by name.

        Args:
            name: The registration name.

        Returns:
            The resolved instance, or None if not found.
        """
        with self._lock:
            self._resolution_count += 1

            if name in self._singletons:
                return self._singletons[name]

            factory_entry = self._factories.get(name)
            if factory_entry is not None:
                factory, args, kwargs = factory_entry
                instance = factory(*args, **kwargs)
                self._singletons[name] = instance
                del self._factories[name]
                self._type_map[type(instance)] = name
                return instance

        return None

    def resolve_by_type(self, cls: Type) -> Any:
        """Resolve a singleton by its type.

        Args:
            cls: The class type to look up.

        Returns:
            The resolved instance, or None.
        """
        with self._lock:
            name = self._type_map.get(cls)
        if name is not None:
            return self.resolve(name)
        return None

    def has(self, name: str) -> bool:
        with self._lock:
            return name in self._singletons or name in self._factories

    def has_type(self, cls: Type) -> bool:
        with self._lock:
            return cls in self._type_map

    def unregister(self, name: str) -> bool:
        with self._lock:
            removed = False
            if name in self._singletons:
                del self._singletons[name]
                removed = True
            if name in self._factories:
                del self._factories[name]
                removed = True
            if removed:
                self._registration_count += 1
            return removed

    def clear(self) -> None:
        with self._lock:
            self._singletons.clear()
            self._factories.clear()
            self._type_map.clear()
            self._registration_count += 1
        logger.info("Discovery container cleared.")

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "singleton_count": len(self._singletons),
                "factory_count": len(self._factories),
                "type_map_count": len(self._type_map),
                "resolution_count": self._resolution_count,
                "registration_count": self._registration_count,
                "singletons": sorted(self._singletons.keys()),
                "factories": sorted(self._factories.keys()),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"DiscoveryContainer(singletons={len(self._singletons)}, "
                f"factories={len(self._factories)})"
            )
