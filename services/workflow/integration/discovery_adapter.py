"""Discovery Adapter — service discovery integration for dynamic endpoint resolution.

Integrates with the ICYQuant service discovery layer to:

* Register workflow nodes as discoverable services
* Resolve downstream service endpoints at runtime
* Track service health and availability
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DiscoveryAdapter:
    """Service discovery integration for the workflow platform.

    Usage::

        adapter = DiscoveryAdapter()
        await adapter.start()
        endpoints = await adapter.discover("oms-service")
    """

    def __init__(self, *, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or {}
        self._lock = threading.RLock()
        self._started = False
        self._services: Dict[str, List[str]] = {}  # service_name → endpoints
        self._instances: Dict[str, Dict[str, Any]] = {}  # instance_id → metadata

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._started = True
        logger.info("DiscoveryAdapter: started")

    async def stop(self) -> None:
        self._started = False
        logger.info("DiscoveryAdapter: stopped")

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register(
        self,
        service_name: str,
        endpoint: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Register a service endpoint."""
        with self._lock:
            if service_name not in self._services:
                self._services[service_name] = []
            if endpoint not in self._services[service_name]:
                self._services[service_name].append(endpoint)
            self._instances[endpoint] = {
                "service_name": service_name,
                "metadata": metadata or {},
            }
        logger.debug("DiscoveryAdapter: registered %s → %s", service_name, endpoint)
        return endpoint

    async def deregister(self, endpoint: str) -> None:
        """Remove a service endpoint."""
        with self._lock:
            instance = self._instances.pop(endpoint, None)
            if instance:
                name = instance["service_name"]
                if name in self._services:
                    self._services[name] = [e for e in self._services[name] if e != endpoint]

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    async def discover(self, service_name: str) -> List[str]:
        """Discover endpoints for a service."""
        with self._lock:
            return list(self._services.get(service_name, []))

    async def discover_one(self, service_name: str) -> Optional[str]:
        """Discover a single endpoint (load-balanced)."""
        endpoints = await self.discover(service_name)
        if not endpoints:
            return None
        import random
        return random.choice(endpoints)

    async def list_services(self) -> List[str]:
        with self._lock:
            return list(self._services.keys())

    async def get_instance_metadata(self, endpoint: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            instance = self._instances.get(endpoint)
            return instance.get("metadata") if instance else None

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    async def sync(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "services": len(self._services),
                "instances": len(self._instances),
                "service_names": list(self._services.keys()),
            }

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "services": len(self._services),
                "total_instances": len(self._instances),
                "services_detail": {
                    name: len(eps) for name, eps in self._services.items()
                },
            }
