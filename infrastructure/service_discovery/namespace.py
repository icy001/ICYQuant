"""Namespace management for service discovery.

Provides ``Namespace`` and ``NamespaceManager`` for organizing
services into isolated namespaces with thread-safe management and
predefined default namespaces for the ICYQuant trading lifecycle.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .exceptions import NamespaceError

logger = logging.getLogger(__name__)

DEFAULT_NAMESPACES = (
    "development",
    "testing",
    "staging",
    "production",
    "research",
    "simulation",
    "live-trading",
)


class Namespace:
    """A logical namespace grouping related services.

    Args:
        name: The namespace name.
        description: Optional human-readable description.
    """

    __slots__ = ("name", "description", "created_at", "_services", "_lock")

    def __init__(self, name: str, description: str = "") -> None:
        if not name:
            raise NamespaceError("Namespace name cannot be empty.")
        self.name = name
        self.description = description or ""
        self.created_at = datetime.utcnow()
        self._services: set = set()
        self._lock = threading.RLock()

    def add_service(self, service_name: str) -> None:
        """Associate a service with this namespace.

        Args:
            service_name: The logical service name to add.
        """
        if not service_name:
            raise NamespaceError("Service name cannot be empty.")
        with self._lock:
            self._services.add(service_name)

    def remove_service(self, service_name: str) -> None:
        """Disassociate a service from this namespace.

        Args:
            service_name: The logical service name to remove.
        """
        with self._lock:
            self._services.discard(service_name)

    def get_services(self) -> List[str]:
        """Return the services registered in this namespace.

        Returns:
            A sorted list of service names.
        """
        with self._lock:
            return sorted(self._services)

    def has_service(self, service_name: str) -> bool:
        """Check whether a service is registered in this namespace.

        Args:
            service_name: The service name to check.

        Returns:
            True if the service is registered.
        """
        with self._lock:
            return service_name in self._services

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the namespace to a dictionary."""
        with self._lock:
            services = sorted(self._services)
        return {
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "service_count": len(services),
            "services": services,
        }

    def __repr__(self) -> str:
        return f"Namespace(name={self.name!r}, services={len(self._services)})"


class NamespaceManager:
    """Manages the set of namespaces for service discovery.

    Pre-populates a set of default namespaces suitable for the
    ICYQuant trading lifecycle. All operations are thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._namespaces: Dict[str, Namespace] = {}
        self._init_defaults()

    def _init_defaults(self) -> None:
        """Create the default namespaces."""
        for name in DEFAULT_NAMESPACES:
            description = self._default_description(name)
            self._namespaces[name] = Namespace(name, description)

    @staticmethod
    def _default_description(name: str) -> str:
        descriptions = {
            "development": "Local development environment.",
            "testing": "Automated testing environment.",
            "staging": "Pre-production staging environment.",
            "production": "Production environment.",
            "research": "Quantitative research environment.",
            "simulation": "Trading simulation environment.",
            "live-trading": "Live trading execution environment.",
        }
        return descriptions.get(name, "")

    def create_namespace(self, name: str, description: str = "") -> Namespace:
        """Create a new namespace.

        Args:
            name: The namespace name.
            description: Optional human-readable description.

        Returns:
            The newly created ``Namespace``.

        Raises:
            NamespaceError: If the namespace already exists.
        """
        if not name:
            raise NamespaceError("Namespace name cannot be empty.")
        with self._lock:
            if name in self._namespaces:
                raise NamespaceError(f"Namespace '{name}' already exists.")
            namespace = Namespace(name, description)
            self._namespaces[name] = namespace
            logger.info("Created namespace '%s'.", name)
            return namespace

    def delete_namespace(self, name: str) -> None:
        """Delete a namespace.

        Args:
            name: The namespace name.

        Raises:
            NamespaceError: If the namespace does not exist or is a
                protected default namespace.
        """
        if name in DEFAULT_NAMESPACES:
            raise NamespaceError(
                f"Cannot delete protected default namespace '{name}'."
            )
        with self._lock:
            if name not in self._namespaces:
                raise NamespaceError(f"Namespace '{name}' does not exist.")
            del self._namespaces[name]
            logger.info("Deleted namespace '%s'.", name)

    def get_namespace(self, name: str) -> Optional[Namespace]:
        """Return a namespace by name.

        Args:
            name: The namespace name.

        Returns:
            The ``Namespace`` or None if not found.
        """
        with self._lock:
            return self._namespaces.get(name)

    def list_namespaces(self) -> List[Namespace]:
        """Return all registered namespaces.

        Returns:
            A list of ``Namespace`` objects sorted by name.
        """
        with self._lock:
            return [self._namespaces[n] for n in sorted(self._namespaces)]

    def add_service_to_namespace(self, namespace: str, service_name: str) -> None:
        """Associate a service with a namespace.

        Args:
            namespace: The namespace name.
            service_name: The service name to add.

        Raises:
            NamespaceError: If the namespace does not exist.
        """
        with self._lock:
            ns = self._namespaces.get(namespace)
            if ns is None:
                raise NamespaceError(f"Namespace '{namespace}' does not exist.")
            ns.add_service(service_name)

    def get_services_in_namespace(self, namespace: str) -> List[str]:
        """Return the services registered in a namespace.

        Args:
            namespace: The namespace name.

        Returns:
            A list of service names. Returns an empty list if the
            namespace does not exist.

        Raises:
            NamespaceError: If the namespace does not exist.
        """
        with self._lock:
            ns = self._namespaces.get(namespace)
            if ns is None:
                raise NamespaceError(f"Namespace '{namespace}' does not exist.")
            return ns.get_services()

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for all namespaces.

        Returns:
            A dictionary with namespace counts and per-namespace
            service counts.
        """
        with self._lock:
            namespaces = [ns.to_dict() for ns in self._namespaces.values()]
        total_services = sum(ns["service_count"] for ns in namespaces)
        return {
            "total_namespaces": len(namespaces),
            "total_services": total_services,
            "default_namespaces": list(DEFAULT_NAMESPACES),
            "namespaces": namespaces,
        }

    def __repr__(self) -> str:
        return f"NamespaceManager(namespaces={len(self._namespaces)})"
