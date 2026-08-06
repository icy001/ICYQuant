"""Discovery Adapter — integrates the Scheduler with Service Discovery.

The :class:`DiscoveryAdapter` enables the scheduler to dynamically
discover available services and workers:
* Service registration and deregistration
* Health-aware instance discovery
* Metadata-based filtering
* Zone/region-aware routing

Architecture::

    Service Discovery ──→ DiscoveryAdapter ──→ Scheduler
                              │
                    Register / Discover / Health
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ServiceInstance:
    """Represents a discovered service instance."""

    def __init__(
        self,
        service_id: str,
        service_name: str,
        host: str,
        port: int,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, str]] = None,
        healthy: bool = True,
    ) -> None:
        self.service_id = service_id
        self.service_name = service_name
        self.host = host
        self.port = port
        self.tags = tags or []
        self.metadata = metadata or {}
        self.healthy = healthy
        self.registered_at: Optional[datetime] = None
        self.last_heartbeat: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_id": self.service_id,
            "service_name": self.service_name,
            "host": self.host,
            "port": self.port,
            "tags": self.tags,
            "metadata": self.metadata,
            "healthy": self.healthy,
        }


class DiscoveryAdapter:
    """Adapter for service discovery integration.

    Responsibilities:
    * Register the scheduler with service discovery
    * Discover worker and service instances
    * Filter by health, tags, metadata, zone
    * Track instance health via heartbeats

    Usage::

        adapter = DiscoveryAdapter()
        await adapter.connect()
        await adapter.register(instance)
        workers = await adapter.discover("worker", tags=["gpu"])
    """

    def __init__(self, discovery_service: Any = None) -> None:
        self._service = discovery_service
        self._lock = threading.Lock()
        self._connected = False
        self._instances: Dict[str, ServiceInstance] = {}
        self._local_instance: Optional[ServiceInstance] = None
        self._discover_count: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def instance_count(self) -> int:
        return len(self._instances)

    @property
    def discover_count(self) -> int:
        return self._discover_count

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the service discovery system."""
        logger.info("DiscoveryAdapter: connecting")
        if self._service and hasattr(self._service, "connect"):
            await self._service.connect()
        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect, deregistering local instance."""
        if self._local_instance:
            await self.deregister(self._local_instance.service_id)
        self._connected = False
        self._instances.clear()
        logger.info("DiscoveryAdapter: disconnected")

    async def synchronize(self) -> Dict[str, Any]:
        """Synchronize discovery state."""
        return {"connected": self._connected, "instances": len(self._instances)}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register(self, instance: ServiceInstance) -> None:
        """Register a service instance with discovery."""
        instance.registered_at = datetime.now(timezone.utc)
        instance.last_heartbeat = instance.registered_at
        self._instances[instance.service_id] = instance
        logger.info("DiscoveryAdapter: registered %s", instance.service_id)

    async def deregister(self, service_id: str) -> None:
        """Deregister a service instance."""
        self._instances.pop(service_id, None)
        logger.info("DiscoveryAdapter: deregistered %s", service_id)

    async def register_self(self, instance: ServiceInstance) -> None:
        """Register the current scheduler instance."""
        self._local_instance = instance
        await self.register(instance)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    async def discover(
        self,
        service_name: str,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, str]] = None,
        healthy_only: bool = True,
    ) -> List[ServiceInstance]:
        """Discover service instances matching criteria."""
        self._discover_count += 1

        results = []
        for instance in self._instances.values():
            if instance.service_name != service_name:
                continue
            if healthy_only and not instance.healthy:
                continue
            if tags and not all(t in instance.tags for t in tags):
                continue
            if metadata:
                match = all(instance.metadata.get(k) == v for k, v in metadata.items())
                if not match:
                    continue
            results.append(instance)

        return results

    async def discover_one(
        self,
        service_name: str,
        tags: Optional[List[str]] = None,
    ) -> Optional[ServiceInstance]:
        """Discover a single healthy instance."""
        instances = await self.discover(service_name, tags=tags, healthy_only=True)
        return instances[0] if instances else None

    async def list_services(self) -> List[str]:
        """List all known service names."""
        return sorted(set(i.service_name for i in self._instances.values()))

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def heartbeat(self, service_id: str) -> None:
        """Send a heartbeat for a service instance."""
        instance = self._instances.get(service_id)
        if instance:
            instance.last_heartbeat = datetime.now(timezone.utc)
            instance.healthy = True

    async def mark_unhealthy(self, service_id: str) -> None:
        """Mark a service instance as unhealthy."""
        instance = self._instances.get(service_id)
        if instance:
            instance.healthy = False
            logger.warning("DiscoveryAdapter: %s marked unhealthy", service_id)

    async def mark_healthy(self, service_id: str) -> None:
        """Mark a service instance as healthy."""
        instance = self._instances.get(service_id)
        if instance:
            instance.healthy = True
