"""
Feature flag dependency injection container.

Provides a simple DI container for registering
and resolving platform services. Ensures
consistent singleton lifecycle for all
feature flag platform components.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Type

logger = logging.getLogger(__name__)


class ServiceContainer:
    """
    Simple dependency injection container.

    Supports singleton and transient lifecycle
    for all feature flag platform services.

    Usage:
        container = ServiceContainer()
        container.register_singleton(MyService)
        svc = container.resolve(MyService)
    """

    def __init__(self) -> None:
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._transients: Dict[str, Callable] = {}

    def register_singleton(
        self,
        service_type: Type,
        instance: Optional[Any] = None,
        factory: Optional[Callable] = None,
    ) -> None:
        """
        Register a service as a singleton.

        Args:
            service_type: The service class.
            instance: Pre-created instance.
            factory: Factory function to create instance.
        """
        key = self._get_key(service_type)

        if instance is not None:
            self._singletons[key] = instance
        elif factory is not None:
            self._factories[key] = factory
        else:
            # Create instance directly
            self._singletons[key] = service_type()

    def register_transient(
        self,
        service_type: Type,
        factory: Callable,
    ) -> None:
        """
        Register a service with transient lifecycle.

        A new instance is created each time resolve is called.

        Args:
            service_type: The service class.
            factory: Factory function to create instance.
        """
        key = self._get_key(service_type)
        self._transients[key] = factory

    def resolve(self, service_type: Type) -> Any:
        """
        Resolve a service from the container.

        Args:
            service_type: The service class.

        Returns:
            Service instance.

        Raises:
            KeyError: If service is not registered.
        """
        key = self._get_key(service_type)

        # Check singletons (already created)
        if key in self._singletons:
            return self._singletons[key]

        # Check factories (lazy singleton creation)
        if key in self._factories:
            instance = self._factories[key]()
            self._singletons[key] = instance
            return instance

        # Check transients
        if key in self._transients:
            return self._transients[key]()

        raise KeyError(f"Service '{key}' not registered in container")

    def try_resolve(self, service_type: Type) -> Optional[Any]:
        """
        Try to resolve a service, returning None if not found.

        Args:
            service_type: The service class.

        Returns:
            Service instance or None.
        """
        try:
            return self.resolve(service_type)
        except KeyError:
            return None

    def is_registered(self, service_type: Type) -> bool:
        """
        Check if a service is registered.

        Args:
            service_type: The service class.

        Returns:
            True if registered.
        """
        key = self._get_key(service_type)
        return (
            key in self._singletons
            or key in self._factories
            or key in self._transients
        )

    def unregister(self, service_type: Type) -> None:
        """
        Unregister a service.

        Args:
            service_type: The service class.
        """
        key = self._get_key(service_type)
        self._singletons.pop(key, None)
        self._factories.pop(key, None)
        self._transients.pop(key, None)

    def clear(self) -> None:
        """Clear all registrations."""
        self._singletons.clear()
        self._factories.clear()
        self._transients.clear()

    def get_registered_types(self) -> list:
        """Get list of registered type names."""
        keys = set()
        keys.update(self._singletons.keys())
        keys.update(self._factories.keys())
        keys.update(self._transients.keys())
        return sorted(keys)

    def get_stats(self) -> Dict[str, Any]:
        """Get container statistics."""
        return {
            "singletons": len(self._singletons),
            "factories": len(self._factories),
            "transients": len(self._transients),
            "total": (
                len(self._singletons)
                + len(self._factories)
                + len(self._transients)
            ),
        }

    @staticmethod
    def _get_key(service_type: Type) -> str:
        """Get a string key for a service type."""
        if isinstance(service_type, type):
            return service_type.__name__
        return str(service_type)
