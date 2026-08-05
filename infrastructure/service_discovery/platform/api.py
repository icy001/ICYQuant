"""Discovery API for ICYQuant service discovery platform.

Provides ``DiscoveryAPI`` as a high-level API combining
gateway, service, topology, and snapshot operations.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .runtime_context import DiscoveryContext

logger = logging.getLogger(__name__)


class DiscoveryAPI:
    """High-level unified API for service discovery.

    Combines gateway, discovery service, topology, and
    snapshot operations into a single entry point.
    """

    def __init__(
        self, context: Optional[DiscoveryContext] = None
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or DiscoveryContext()
        self._gateway = self._context.get("gateway")
        self._service = self._context.get("discovery_service")
        self._topology = self._context.get("topology")
        self._snapshot = self._context.get("snapshot_api")
        self._request_count = 0
        self._last_request: Optional[Dict[str, Any]] = None

    async def register(
        self, instance: Any, **kwargs: Any
    ) -> Dict[str, Any]:
        self._request_count += 1
        if self._gateway:
            return await self._gateway.register_service(
                instance, **kwargs
            )
        if self._service:
            return await self._service.register(instance)
        return {"success": False, "error": "No service available"}

    async def discover(
        self, service_name: str, **kwargs: Any
    ) -> List[Any]:
        self._request_count += 1
        if self._gateway:
            return await self._gateway.discover_service(
                service_name, **kwargs
            )
        if self._service:
            result = await self._service.resolve(
                service_name, **kwargs
            )
            return result.get("instances", [])
        return []

    async def list_services(
        self, namespace: str = "default"
    ) -> List[Any]:
        self._request_count += 1
        if self._gateway:
            return await self._gateway.list_services(namespace)
        return []

    async def health(self) -> Dict[str, Any]:
        self._request_count += 1
        if self._gateway:
            return await self._gateway.health_check()
        return {"healthy": False, "error": "No gateway"}

    async def topology(self) -> Dict[str, Any]:
        self._request_count += 1
        if self._topology:
            get_fn = getattr(
                self._topology, "get_topology", None
            )
            if callable(get_fn):
                result = get_fn()
                if asyncio.iscoroutine(result):
                    return await result
                return result
        return {"error": "No topology service"}

    async def snapshot(self) -> Dict[str, Any]:
        self._request_count += 1
        if self._gateway:
            return await self._gateway.get_snapshot()
        if self._snapshot:
            export_fn = getattr(self._snapshot, "export", None)
            if callable(export_fn):
                result = export_fn()
                if asyncio.iscoroutine(result):
                    return await result
                return result
        return {"error": "No snapshot service"}

    def get_context(self) -> DiscoveryContext:
        return self._context

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "request_count": self._request_count,
                "gateway_available": self._gateway is not None,
                "service_available": self._service is not None,
                "topology_available": self._topology is not None,
                "snapshot_available": self._snapshot is not None,
                "components": self._context.list_components(),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"DiscoveryAPI(requests={self._request_count})"
            )
