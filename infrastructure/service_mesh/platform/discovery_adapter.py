"""Service Discovery Adapter for the Service Mesh Platform.

Provides ``ServiceDiscoveryAdapter`` for integrating service
discovery with the mesh resolver and routing.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .telemetry import PlatformTelemetry
from .metrics import PlatformMetrics

logger = logging.getLogger(__name__)


class ServiceRegistration:
    """Represents a registered service."""

    _counter = 0

    def __init__(
        self,
        service_name: str,
        service_id: Optional[str] = None,
        version: str = "v1",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.service_name = service_name
        ServiceRegistration._counter += 1
        self.service_id = (
            service_id
            or f"{service_name}-{int(time.monotonic())}-{ServiceRegistration._counter}"
        )
        self.version = version
        self.metadata = metadata or {}
        self.status = "registered"
        self.registered_at = datetime.utcnow()
        self.last_updated: Optional[datetime] = None

    def update(self, metadata: Dict[str, Any]) -> None:
        self.metadata.update(metadata)
        self.last_updated = datetime.utcnow()

    def deregister(self) -> None:
        self.status = "deregistered"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_id": self.service_id,
            "service_name": self.service_name,
            "version": self.version,
            "status": self.status,
            "metadata": self.metadata,
            "registered_at": self.registered_at.isoformat(),
            "last_updated": (
                self.last_updated.isoformat()
                if self.last_updated
                else None
            ),
        }


class ServiceDiscoveryAdapter:
    """Adapter for integrating service discovery with the mesh."""

    def __init__(
        self,
        telemetry: Optional[PlatformTelemetry] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._telemetry = telemetry or PlatformTelemetry()
        self._metrics = metrics or PlatformMetrics()
        self._services: Dict[str, ServiceRegistration] = {}
        self._name_index: Dict[str, List[str]] = {}
        self._resolver_handlers: Dict[str, Callable] = {}
        self._discovery_active = False

    async def initialize(self) -> Dict[str, Any]:
        self._discovery_active = True
        self._telemetry.log_platform_event(
            "service_discovery_initialized", "discovery",
        )
        logger.info("Service discovery adapter initialized.")
        return {"success": True}

    async def shutdown(self) -> Dict[str, Any]:
        self._discovery_active = False
        self._telemetry.log_platform_event(
            "service_discovery_shutdown", "discovery",
        )
        logger.info("Service discovery adapter shut down.")
        return {"success": True}

    @property
    def is_active(self) -> bool:
        return self._discovery_active

    def register_resolver_handler(
        self,
        resolver_type: str,
        handler: Callable,
    ) -> None:
        self._resolver_handlers[resolver_type] = handler

    async def register_service(
        self,
        service_name: str,
        version: str = "v1",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Register a service with the mesh."""
        registration = ServiceRegistration(
            service_name,
            version=version,
            metadata=metadata,
        )

        with self._lock:
            self._services[registration.service_id] = registration
            if service_name not in self._name_index:
                self._name_index[service_name] = []
            self._name_index[service_name].append(
                registration.service_id
            )

        self._metrics.increment_counter(
            "icyquant_mesh_services_registered_total",
            labels={"service": service_name},
        )
        self._telemetry.log_platform_event(
            "service_registered", "discovery",
            {"service_name": service_name,
             "service_id": registration.service_id},
        )
        logger.info(
            "Service '%s' registered as '%s'.",
            service_name,
            registration.service_id,
        )
        return registration.to_dict()

    async def deregister_service(
        self, service_id: str
    ) -> Dict[str, Any]:
        """Deregister a service."""
        registration = self._services.get(service_id)
        if registration is None:
            return {
                "success": False,
                "error": "Service not found",
            }

        registration.deregister()
        with self._lock:
            self._services.pop(service_id, None)
            name = registration.service_name
            if name in self._name_index:
                ids = self._name_index[name]
                if service_id in ids:
                    ids.remove(service_id)

        self._telemetry.log_platform_event(
            "service_deregistered", "discovery",
            {"service_id": service_id},
        )
        return {"success": True, "service_id": service_id}

    async def resolve_service(
        self,
        service_name: str,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resolve a service by name."""
        service_ids = self._name_index.get(service_name, [])
        services = []
        for sid in service_ids:
            reg = self._services.get(sid)
            if reg and reg.status == "registered":
                if version is None or reg.version == version:
                    services.append(reg.to_dict())

        if not services:
            return {
                "success": False,
                "error": f"Service '{service_name}' not found",
            }

        # Apply resolver
        resolver_handler = self._resolver_handlers.get(
            "default"
        )
        if resolver_handler:
            try:
                result = resolver_handler(services)
                if asyncio.iscoroutine(result):
                    result = await result
                return {
                    "success": True,
                    "service": service_name,
                    "resolved": result,
                }
            except Exception:
                pass

        return {
            "success": True,
            "service": service_name,
            "instances": services,
        }

    def list_services(
        self, service_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if service_name:
            ids = self._name_index.get(service_name, [])
            return [
                self._services[sid].to_dict()
                for sid in ids
                if sid in self._services
            ]
        return [
            s.to_dict() for s in self._services.values()
        ]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "active": self._discovery_active,
                "total_services": len(self._services),
                "service_names": list(self._name_index.keys()),
                "resolver_handlers": list(
                    self._resolver_handlers.keys()
                ),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"ServiceDiscoveryAdapter("
                f"services={len(self._services)}, "
                f"active={self._discovery_active})"
            )
