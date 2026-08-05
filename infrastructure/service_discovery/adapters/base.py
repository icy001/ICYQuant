"""Abstract registry adapter for service discovery backends.

Defines the ``RegistryAdapter`` abstract base class that all backend
adapters (memory, etcd, consul, kubernetes) must implement, providing
a uniform interface for registration, discovery, heartbeat, and
lifecycle management of service instances.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..instance import ServiceInstance
from ..service import Service

logger = logging.getLogger(__name__)


class RegistryAdapter(ABC):
    """Abstract base class for a service registry backend adapter.

    All adapters must implement connection management, registration,
    discovery, heartbeat, and update operations. Implementations are
    expected to be safe for concurrent use.
    """

    @abstractmethod
    async def register(self, instance: ServiceInstance) -> None:
        """Register a service instance with the backend."""

    @abstractmethod
    async def deregister(self, service_name: str, instance_id: str) -> None:
        """Deregister a service instance from the backend."""

    @abstractmethod
    async def discover(
        self,
        service_name: str,
        namespace: str = "default",
        version: str = None,
    ) -> List[ServiceInstance]:
        """Discover service instances matching the given criteria."""

    @abstractmethod
    async def get_service(
        self, service_name: str, namespace: str = "default"
    ) -> Optional[Service]:
        """Return a service aggregate by name."""

    @abstractmethod
    async def list_services(self, namespace: str = "default") -> List[Service]:
        """List all services in a namespace."""

    @abstractmethod
    async def heartbeat(self, service_name: str, instance_id: str) -> None:
        """Renew the lease for a service instance."""

    @abstractmethod
    async def update_instance(
        self, service_name: str, instance_id: str, updates: Dict[str, Any]
    ) -> None:
        """Update fields of a registered service instance."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish a connection to the backend."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection to the backend."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Return whether the adapter is currently connected."""

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Return adapter-specific statistics."""
