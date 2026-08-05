"""Service Discovery integration for the Service Mesh.

Provides ``MeshDiscovery`` for integrating with the existing
Service Discovery platform to automatically discover services,
resolve endpoints, and enable traffic routing.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .context import MeshContext
from .events import MeshEvent, MeshEventPublisher
from .models import MeshService, RoutingRule
from .exceptions import MeshServiceNotFoundError

logger = logging.getLogger(__name__)


class MeshDiscovery:
    """Service discovery integration for the mesh."""

    def __init__(
        self,
        context: Optional[MeshContext] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or MeshContext()
        self._publisher: Optional[MeshEventPublisher] = None
        self._discovery_client: Optional[Any] = None
        self._services: Dict[str, MeshService] = {}
        self._routing_rules: Dict[str, RoutingRule] = {}
        self._discover_count = 0
        self._sync_count = 0

        self._context.register("discovery", self)

    def set_publisher(self, publisher: MeshEventPublisher) -> None:
        self._publisher = publisher

    def set_discovery_client(self, client: Any) -> None:
        self._discovery_client = client

    async def discover_services(
        self, namespace: Optional[str] = None
    ) -> Dict[str, Any]:
        """Discover services from the service discovery platform."""
        with self._lock:
            self._discover_count += 1

        # Try to use the existing discovery client
        if self._discovery_client:
            try:
                services = await self._discovery_client.list_services(
                    namespace=namespace
                )
                if isinstance(services, list):
                    for svc_data in services:
                        if isinstance(svc_data, dict):
                            svc = MeshService(
                                name=svc_data.get("name", "unknown"),
                                namespace=svc_data.get(
                                    "namespace", "default"
                                ),
                                version=svc_data.get(
                                    "version", "v1"
                                ),
                            )
                            with self._lock:
                                self._services[svc.service_id] = svc
                return {
                    "success": True,
                    "services_found": len(self._services),
                }
            except Exception as exc:
                logger.warning(
                    "Discovery client failed: %s", exc
                )

        # Fallback: return currently known services
        with self._lock:
            return {
                "success": True,
                "services_found": len(self._services),
                "services": [
                    s.to_dict() for s in self._services.values()
                ],
            }

    def register_service(
        self,
        name: str,
        namespace: str = "default",
        version: str = "v1",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MeshService:
        """Register a service with the mesh discovery."""
        svc = MeshService(
            name=name,
            namespace=namespace,
            version=version,
            metadata=metadata,
        )
        with self._lock:
            self._services[svc.service_id] = svc
        logger.info(
            "Service %s registered in mesh discovery.",
            svc.service_id,
        )
        return svc

    def deregister_service(
        self, service_id: str
    ) -> bool:
        with self._lock:
            if service_id in self._services:
                del self._services[service_id]
                return True
        return False

    def get_service(self, service_id: str) -> Optional[MeshService]:
        with self._lock:
            return self._services.get(service_id)

    def list_services(
        self, namespace: Optional[str] = None
    ) -> List[MeshService]:
        with self._lock:
            services = list(self._services.values())
        if namespace:
            services = [
                s for s in services if s.namespace == namespace
            ]
        return services

    def add_routing_rule(
        self, rule: RoutingRule
    ) -> None:
        with self._lock:
            self._routing_rules[rule.rule_id] = rule

    def get_routing_rules(
        self, service: Optional[str] = None
    ) -> List[RoutingRule]:
        with self._lock:
            rules = list(self._routing_rules.values())
        if service:
            rules = [r for r in rules if r.service == service]
        return rules

    async def sync(
        self,
        control_plane: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Synchronize discovery state with control plane."""
        with self._lock:
            self._sync_count += 1

        if control_plane:
            for rule in self._routing_rules.values():
                control_plane.add_routing_rule(rule)

            result = await control_plane.publish_configuration(
                "routing"
            )
            return {
                "success": True,
                "sync_count": self._sync_count,
                "services_count": len(self._services),
                "rules_count": len(self._routing_rules),
                "publish_result": result,
            }

        return {
            "success": True,
            "sync_count": self._sync_count,
            "services_count": len(self._services),
            "rules_count": len(self._routing_rules),
        }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "services_count": len(self._services),
                "routing_rules_count": len(self._routing_rules),
                "discover_count": self._discover_count,
                "sync_count": self._sync_count,
                "has_discovery_client": bool(
                    self._discovery_client
                ),
            }

    def clear(self) -> None:
        with self._lock:
            self._services.clear()
            self._routing_rules.clear()
            self._discover_count = 0
            self._sync_count = 0

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"MeshDiscovery(services={len(self._services)}, "
                f"rules={len(self._routing_rules)})"
            )
