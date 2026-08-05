"""Service discovery platform for ICYQuant.

Provides ``DiscoveryPlatform`` as the unified entry point for
managing the full service discovery stack: registry, resolver,
heartbeat, HA controller, gateway, and lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .runtime_context import DiscoveryContext

logger = logging.getLogger(__name__)


class DiscoveryPlatform:
    """Unified platform entry point for service discovery.

    Provides a clean API for registering, discovering, listing,
    and managing services, backed by integrated registry,
    resolver, heartbeat, HA, gateway, and lifecycle components.

    Args:
        context: Optional ``DiscoveryContext`` instance.
    """

    def __init__(self, context: Optional[DiscoveryContext] = None) -> None:
        self._lock = threading.RLock()
        self._context = context or DiscoveryContext()
        self._registry: Any = None
        self._resolver: Any = None
        self._heartbeat: Any = None
        self._ha: Any = None
        self._gateway: Any = None
        self._lifecycle: Any = None
        self._initialized = False
        self._init_count = 0
        self._register_count = 0
        self._discover_count = 0
        self._last_init: Optional[Dict[str, Any]] = None

    def attach(
        self,
        registry: Any = None,
        resolver: Any = None,
        heartbeat: Any = None,
        ha: Any = None,
        gateway: Any = None,
        lifecycle: Any = None,
    ) -> None:
        """Attach component instances to the platform.

        Args:
            registry: Service registry instance.
            resolver: Service resolver instance.
            heartbeat: Heartbeat service instance.
            ha: HA controller instance.
            gateway: Gateway instance.
            lifecycle: Lifecycle manager instance.
        """
        with self._lock:
            self._registry = registry
            self._resolver = resolver
            self._heartbeat = heartbeat
            self._ha = ha
            self._gateway = gateway
            self._lifecycle = lifecycle

        if registry is not None:
            self._context.register("registry", registry)
        if resolver is not None:
            self._context.register("resolver", resolver)
        if heartbeat is not None:
            self._context.register("heartbeat", heartbeat)
        if ha is not None:
            self._context.register("ha_controller", ha)
        if gateway is not None:
            self._context.register("gateway", gateway)
        if lifecycle is not None:
            self._context.register("lifecycle", lifecycle)

        self._context.register("platform", self)
        logger.info("Discovery platform components attached.")

    async def initialize(self) -> Dict[str, Any]:
        """Initialize the platform.

        Returns:
            A dictionary describing the initialization result.
        """
        with self._lock:
            self._init_count += 1
            self._initialized = True

        result: Dict[str, Any] = {
            "initialized": True,
            "timestamp": datetime.utcnow().isoformat(),
            "components": self._context.list_components(),
        }
        self._last_init = result
        logger.info(
            "Discovery platform initialized with %d components.",
            len(self._context.list_components()),
        )
        return result

    async def register(
        self, instance: Any
    ) -> Dict[str, Any]:
        """Register a service instance.

        Args:
            instance: The service instance to register.

        Returns:
            Registration result dictionary.
        """
        with self._lock:
            self._register_count += 1

        if self._registry is None:
            return {
                "success": False,
                "error": "No registry attached",
            }

        register_fn = getattr(self._registry, "register", None)
        if not callable(register_fn):
            return {
                "success": False,
                "error": "Registry has no register method",
            }

        try:
            coro = register_fn(instance)
            if asyncio.iscoroutine(coro):
                result = await coro
            else:
                result = coro
            if isinstance(result, dict):
                result.setdefault("success", True)
            return result
        except Exception as exc:
            logger.error("Service registration failed: %s", exc)
            return {"success": False, "error": str(exc)}

    async def discover(
        self, service_name: str, **kwargs: Any
    ) -> List[Any]:
        """Discover instances for a service.

        Args:
            service_name: The logical service name.
            **kwargs: Additional resolver arguments.

        Returns:
            List of discovered instances.
        """
        with self._lock:
            self._discover_count += 1

        if self._resolver is None:
            return []

        resolve_fn = getattr(self._resolver, "resolve", None)
        if not callable(resolve_fn):
            return []

        try:
            coro = resolve_fn(service_name, **kwargs)
            if asyncio.iscoroutine(coro):
                result = await coro
            else:
                result = coro
            if isinstance(result, list):
                return result
            if isinstance(result, dict) and "instances" in result:
                return result["instances"]
            return []
        except Exception as exc:
            logger.error("Service discovery failed: %s", exc)
            return []

    async def shutdown(self) -> Dict[str, Any]:
        """Shutdown the platform gracefully.

        Returns:
            Shutdown result dictionary.
        """
        with self._lock:
            self._initialized = False

        result: Dict[str, Any] = {
            "shutdown": True,
            "timestamp": datetime.utcnow().isoformat(),
        }
        logger.info("Discovery platform shutting down.")
        return result

    def is_initialized(self) -> bool:
        with self._lock:
            return self._initialized

    def get_context(self) -> DiscoveryContext:
        return self._context

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "initialized": self._initialized,
                "init_count": self._init_count,
                "register_count": self._register_count,
                "discover_count": self._discover_count,
                "attached_components": {
                    "registry": self._registry is not None,
                    "resolver": self._resolver is not None,
                    "heartbeat": self._heartbeat is not None,
                    "ha": self._ha is not None,
                    "gateway": self._gateway is not None,
                    "lifecycle": self._lifecycle is not None,
                },
                "context_stats": self._context.get_stats(),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"DiscoveryPlatform(initialized={self._initialized}, "
                f"registers={self._register_count})"
            )
