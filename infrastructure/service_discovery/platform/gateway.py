"""Service discovery gateway for ICYQuant platform.

Provides ``ServiceDiscoveryGateway`` as a unified API layer
for register, discover, list, health, topology, and snapshot
operations. Supports REST API, gRPC (reserved), and internal SDK.
"""

from __future__ import annotations

import asyncio
import logging
import time
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .runtime_context import DiscoveryContext
from .monitoring import PlatformMetrics

logger = logging.getLogger(__name__)


class ServiceDiscoveryGateway:
    """Unified gateway for service discovery operations.

    Provides a consistent API for registering, discovering,
    listing services, checking health, querying topology,
    and accessing snapshots.
    """

    def __init__(
        self,
        context: Optional[DiscoveryContext] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or DiscoveryContext()
        self._metrics = metrics or PlatformMetrics()
        self._request_count = 0
        self._last_request: Optional[Dict[str, Any]] = None
        self._routes: Dict[str, Any] = {}

    async def register_service(
        self, instance: Any, **kwargs: Any
    ) -> Dict[str, Any]:
        """Register a service instance.

        Args:
            instance: The service instance to register.
            **kwargs: Additional arguments.

        Returns:
            Registration result.
        """
        start = time.monotonic()
        self._request_count += 1

        registry = self._context.get("registry")
        if registry is None:
            self._record_request("register", "POST", 500, start)
            return {"success": False, "error": "Registry not available"}

        try:
            register_fn = getattr(registry, "register", None)
            if register_fn is None:
                self._record_request("register", "POST", 500, start)
                return {
                    "success": False,
                    "error": "No register method",
                }
            coro = register_fn(instance)
            if asyncio.iscoroutine(coro):
                result = await coro
            else:
                result = coro
            self._record_request("register", "POST", 200, start)
            if isinstance(result, dict):
                result.setdefault("success", True)
            return result
        except Exception as exc:
            self._record_request("register", "POST", 500, start)
            logger.error("Gateway register failed: %s", exc)
            return {"success": False, "error": str(exc)}

    async def discover_service(
        self, service_name: str, **kwargs: Any
    ) -> List[Any]:
        """Discover instances for a service.

        Args:
            service_name: Logical service name.
            **kwargs: Additional arguments.

        Returns:
            List of discovered instances.
        """
        start = time.monotonic()
        self._request_count += 1

        resolver = self._context.get("resolver")
        if resolver is None:
            self._record_request("discover", "GET", 500, start)
            return []

        try:
            resolve_fn = getattr(resolver, "resolve", None)
            if resolve_fn is None:
                self._record_request("discover", "GET", 500, start)
                return []
            coro = resolve_fn(service_name, **kwargs)
            if asyncio.iscoroutine(coro):
                result = await coro
            else:
                result = coro
            self._record_request("discover", "GET", 200, start)
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                return result.get("instances", [])
            return []
        except Exception as exc:
            self._record_request("discover", "GET", 500, start)
            logger.error("Gateway discover failed: %s", exc)
            return []

    async def list_services(
        self, namespace: str = "default"
    ) -> List[Any]:
        """List all services in a namespace.

        Args:
            namespace: Namespace to list from.

        Returns:
            List of services.
        """
        start = time.monotonic()
        self._request_count += 1

        registry = self._context.get("registry")
        if registry is None:
            self._record_request("list", "GET", 500, start)
            return []

        try:
            list_fn = getattr(registry, "list_services", None)
            if list_fn is None:
                self._record_request("list", "GET", 500, start)
                return []
            coro = list_fn(namespace)
            if asyncio.iscoroutine(coro):
                result = await coro
            else:
                result = coro
            self._record_request("list", "GET", 200, start)
            return result if isinstance(result, list) else []
        except Exception as exc:
            self._record_request("list", "GET", 500, start)
            logger.error("Gateway list failed: %s", exc)
            return []

    async def health_check(self) -> Dict[str, Any]:
        """Run gateway health check.

        Returns:
            Health status dictionary.
        """
        self._request_count += 1
        components = {}
        for name in ["registry", "resolver", "heartbeat"]:
            comp = self._context.get(name)
            components[name] = comp is not None

        return {
            "healthy": all(components.values()),
            "components": components,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def get_topology(self) -> Dict[str, Any]:
        """Get service topology information.

        Returns:
            Topology dictionary.
        """
        self._request_count += 1
        topology = self._context.get("topology")
        if topology is not None:
            try:
                get_fn = getattr(topology, "get_topology", None)
                if callable(get_fn):
                    coro = get_fn()
                    if asyncio.iscoroutine(coro):
                        return await coro
                    return coro
            except Exception:
                pass

        return {
            "nodes": self._context.list_components(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def get_snapshot(self) -> Dict[str, Any]:
        """Get current platform snapshot.

        Returns:
            Snapshot dictionary.
        """
        self._request_count += 1
        snapshot_api = self._context.get("snapshot_api")
        if snapshot_api is not None:
            try:
                export_fn = getattr(snapshot_api, "export", None)
                if callable(export_fn):
                    coro = export_fn()
                    if asyncio.iscoroutine(coro):
                        return await coro
                    return coro
            except Exception:
                pass

        return {
            "context": self._context.to_dict(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def register_route(
        self, path: str, handler: Any
    ) -> None:
        with self._lock:
            self._routes[path] = handler

    def _record_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        start: float,
    ) -> None:
        duration = time.monotonic() - start
        self._metrics.record_gateway_request(
            endpoint, method, status_code, duration
        )
        self._last_request = {
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "duration_s": duration,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "request_count": self._request_count,
                "routes": sorted(self._routes.keys()),
                "last_request": self._last_request,
                "metrics": self._metrics.get_stats(),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"ServiceDiscoveryGateway(requests={self._request_count}, "
                f"routes={len(self._routes)})"
            )
