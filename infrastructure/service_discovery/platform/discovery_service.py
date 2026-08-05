"""Discovery service for ICYQuant platform.

Provides ``DiscoveryService`` as the single entry point for
all business modules to register, resolve, heartbeat, and
deregister services.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .runtime_context import DiscoveryContext
from .monitoring import PlatformMetrics

logger = logging.getLogger(__name__)


class DiscoveryService:
    """Single entry point for business modules.

    Provides register, resolve, heartbeat, and deregister
    operations unified across the discovery platform.

    Args:
        context: Optional ``DiscoveryContext`` instance.
        metrics: Optional ``PlatformMetrics`` instance.
    """

    def __init__(
        self,
        context: Optional[DiscoveryContext] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or DiscoveryContext()
        self._metrics = metrics or PlatformMetrics()
        self._register_count = 0
        self._resolve_count = 0
        self._heartbeat_count = 0
        self._deregister_count = 0
        self._registered_services: Dict[str, Any] = {}
        self._last_operation: Optional[Dict[str, Any]] = None

    async def register(
        self,
        instance: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Register a service instance.

        Args:
            instance: The service instance.
            metadata: Optional metadata dictionary.

        Returns:
            Registration result.
        """
        with self._lock:
            self._register_count += 1

        registry = self._context.get("registry")
        if registry is None:
            return {
                "success": False,
                "error": "Registry not available",
            }

        try:
            register_fn = getattr(registry, "register", None)
            if register_fn is None:
                return {
                    "success": False,
                    "error": "No register method on registry",
                }
            coro = register_fn(instance)
            if asyncio.iscoroutine(coro):
                result = await coro
            else:
                result = coro

            service_name = ""
            instance_id = ""
            if hasattr(instance, "service_name"):
                service_name = instance.service_name
            if hasattr(instance, "instance_id"):
                instance_id = instance.instance_id

            self._registered_services[f"{service_name}:{instance_id}"] = (
                instance
            )

            self._metrics.record_runtime(
                "service_registered", service_name
            )

            self._last_operation = {
                "operation": "register",
                "service_name": service_name,
                "instance_id": instance_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

            if isinstance(result, dict):
                result.setdefault("success", True)
                result.setdefault("service_name", service_name)
                result.setdefault("instance_id", instance_id)
            return result
        except Exception as exc:
            logger.error("Service registration failed: %s", exc)
            return {"success": False, "error": str(exc)}

    async def resolve(
        self, service_name: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """Resolve instances for a service.

        Args:
            service_name: Logical service name.
            **kwargs: Additional resolver arguments.

        Returns:
            Resolution result with instances list.
        """
        with self._lock:
            self._resolve_count += 1

        resolver = self._context.get("resolver")
        if resolver is None:
            return {
                "success": False,
                "instances": [],
                "error": "Resolver not available",
            }

        try:
            resolve_fn = getattr(resolver, "resolve", None)
            if resolve_fn is None:
                return {
                    "success": False,
                    "instances": [],
                    "error": "No resolve method on resolver",
                }
            coro = resolve_fn(service_name, **kwargs)
            if asyncio.iscoroutine(coro):
                result = await coro
            else:
                result = coro

            instances = []
            if isinstance(result, list):
                instances = result
            elif isinstance(result, dict):
                instances = result.get("instances", [])

            self._metrics.record_runtime(
                "service_resolved", service_name
            )

            return {
                "success": True,
                "service_name": service_name,
                "instances": instances,
                "count": len(instances),
            }
        except Exception as exc:
            logger.error("Service resolution failed: %s", exc)
            return {
                "success": False,
                "service_name": service_name,
                "instances": [],
                "error": str(exc),
            }

    async def heartbeat(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        """Send a heartbeat for a service instance.

        Args:
            service_name: Logical service name.
            instance_id: Instance identifier.

        Returns:
            Heartbeat result.
        """
        with self._lock:
            self._heartbeat_count += 1

        heartbeat_svc = self._context.get("heartbeat")
        if heartbeat_svc is None:
            return {
                "success": False,
                "error": "Heartbeat service not available",
            }

        try:
            beat_fn = getattr(heartbeat_svc, "send_heartbeat", None)
            if beat_fn is None:
                beat_fn = getattr(heartbeat_svc, "beat", None)
            if beat_fn is None:
                return {
                    "success": False,
                    "error": "No heartbeat method",
                }
            coro = beat_fn(service_name, instance_id)
            if asyncio.iscoroutine(coro):
                result = await coro
            else:
                result = coro

            self._metrics.record_runtime(
                "heartbeat", service_name
            )
            return {
                "success": True,
                "service_name": service_name,
                "instance_id": instance_id,
                "result": result,
            }
        except Exception as exc:
            logger.error("Heartbeat failed: %s", exc)
            return {
                "success": False,
                "service_name": service_name,
                "instance_id": instance_id,
                "error": str(exc),
            }

    async def deregister(
        self,
        service_name: str,
        instance_id: str,
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """Deregister a service instance.

        Args:
            service_name: Logical service name.
            instance_id: Instance identifier.
            namespace: Namespace name.

        Returns:
            Deregistration result.
        """
        with self._lock:
            self._deregister_count += 1

        registry = self._context.get("registry")
        if registry is None:
            return {
                "success": False,
                "error": "Registry not available",
            }

        try:
            deregister_fn = getattr(registry, "deregister", None)
            if deregister_fn is None:
                return {
                    "success": False,
                    "error": "No deregister method",
                }
            coro = deregister_fn(
                service_name, instance_id, namespace
            )
            if asyncio.iscoroutine(coro):
                result = await coro
            else:
                result = coro

            key = f"{service_name}:{instance_id}"
            with self._lock:
                self._registered_services.pop(key, None)

            self._metrics.record_runtime(
                "service_deregistered", service_name
            )

            return {
                "success": True,
                "service_name": service_name,
                "instance_id": instance_id,
                "result": result,
            }
        except Exception as exc:
            logger.error("Deregistration failed: %s", exc)
            return {
                "success": False,
                "service_name": service_name,
                "instance_id": instance_id,
                "error": str(exc),
            }

    def list_registered(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "count": len(self._registered_services),
                "services": sorted(self._registered_services.keys()),
            }

    def get_context(self) -> DiscoveryContext:
        return self._context

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "register_count": self._register_count,
                "resolve_count": self._resolve_count,
                "heartbeat_count": self._heartbeat_count,
                "deregister_count": self._deregister_count,
                "registered_services": len(
                    self._registered_services
                ),
                "last_operation": self._last_operation,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"DiscoveryService(registered={len(self._registered_services)}, "
                f"resolves={self._resolve_count})"
            )
