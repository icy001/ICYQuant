"""Mesh Service Registry for the Service Mesh.

Provides ``MeshRegistry`` for registering, discovering, and
managing mesh services and their sidecar instances.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .context import MeshContext
from .events import MeshEvent, MeshEventPublisher
from .models import MeshService, MeshServiceStatus, SidecarInstance
from .exceptions import MeshServiceError, MeshServiceNotFoundError

logger = logging.getLogger(__name__)


class MeshRegistry:
    """Service registry for the service mesh."""

    def __init__(
        self,
        context: Optional[MeshContext] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or MeshContext()
        self._publisher: Optional[MeshEventPublisher] = None
        self._services: Dict[str, MeshService] = {}
        self._sidecar_map: Dict[str, List[str]] = {}
        self._register_count = 0
        self._deregister_count = 0
        self._discover_count = 0

        self._context.register("mesh_registry", self)

    def set_publisher(self, publisher: MeshEventPublisher) -> None:
        self._publisher = publisher

    def register_service(
        self,
        name: str,
        namespace: str = "default",
        version: str = "v1",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MeshService:
        """Register a service with the mesh."""
        service_id = f"{namespace}/{name}"
        svc = MeshService(
            name=name,
            namespace=namespace,
            version=version,
            status=MeshServiceStatus.RUNNING,
            metadata=metadata,
        )
        with self._lock:
            self._services[service_id] = svc
            self._register_count += 1

        logger.info(
            "Service '%s' registered in mesh registry.",
            service_id,
        )
        return svc

    def deregister_service(
        self, service_id: str
    ) -> Dict[str, Any]:
        """Deregister a service from the mesh."""
        with self._lock:
            if service_id not in self._services:
                return {
                    "success": False,
                    "error": f"Service '{service_id}' not found",
                }
            self._services[service_id].status = (
                MeshServiceStatus.STOPPED
            )
            self._services[service_id].updated_at = (
                datetime.utcnow()
            )
            del self._services[service_id]
            self._deregister_count += 1

        # Clean up sidecar references
        if service_id in self._sidecar_map:
            del self._sidecar_map[service_id]

        return {"success": True, "service_id": service_id}

    def get_service(self, service_id: str) -> Optional[MeshService]:
        with self._lock:
            return self._services.get(service_id)

    def list_services(
        self,
        namespace: Optional[str] = None,
        status: Optional[MeshServiceStatus] = None,
    ) -> List[MeshService]:
        with self._lock:
            services = list(self._services.values())
        if namespace:
            services = [
                s for s in services if s.namespace == namespace
            ]
        if status:
            services = [
                s for s in services if s.status == status
            ]
        return services

    def add_sidecar_to_service(
        self,
        service_id: str,
        sidecar_id: str,
    ) -> None:
        with self._lock:
            if service_id not in self._sidecar_map:
                self._sidecar_map[service_id] = []
            if sidecar_id not in self._sidecar_map[service_id]:
                self._sidecar_map[service_id].append(sidecar_id)

    def remove_sidecar_from_service(
        self,
        service_id: str,
        sidecar_id: str,
    ) -> None:
        with self._lock:
            if service_id in self._sidecar_map:
                self._sidecar_map[service_id] = [
                    s
                    for s in self._sidecar_map[service_id]
                    if s != sidecar_id
                ]

    def get_service_sidecars(
        self, service_id: str
    ) -> List[str]:
        with self._lock:
            return list(self._sidecar_map.get(service_id, []))

    def discover(
        self,
        name: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> List[MeshService]:
        """Discover services by name and namespace."""
        with self._lock:
            self._discover_count += 1
            services = list(self._services.values())
        if name:
            services = [
                s
                for s in services
                if s.name == name
            ]
        if namespace:
            services = [
                s for s in services if s.namespace == namespace
            ]
        return services

    def get_all_services_dict(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                s.to_dict() for s in self._services.values()
            ]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "registered_services": len(self._services),
                "register_count": self._register_count,
                "deregister_count": self._deregister_count,
                "discover_count": self._discover_count,
                "sidecar_assignments": {
                    k: len(v)
                    for k, v in self._sidecar_map.items()
                },
            }

    def clear(self) -> None:
        with self._lock:
            self._services.clear()
            self._sidecar_map.clear()
            self._register_count = 0
            self._deregister_count = 0
            self._discover_count = 0

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"MeshRegistry(services={len(self._services)}, "
                f"sidecars={sum(len(v) for v in self._sidecar_map.values())})"
            )
