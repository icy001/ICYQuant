"""Virtual Service for ICYQuant Service Mesh.

Provides ``VirtualService`` for defining a logical service with
multiple traffic routing rules, supporting weighted traffic split
across versions (stable/canary) and deployment strategies.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .route import (
    RouteDestination,
    RouteMatchType,
    TrafficRoute,
)

logger = logging.getLogger(__name__)


class VirtualService:
    """A virtual service with traffic routing rules."""

    def __init__(
        self,
        name: str,
        namespace: str = "default",
        hosts: Optional[List[str]] = None,
        enabled: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.name = name
        self.namespace = namespace
        self.hosts = hosts or ["*"]
        self.enabled = enabled
        self.metadata = metadata or {}
        self._routes: List[TrafficRoute] = []
        self._default_destinations: List[RouteDestination] = []
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self._lock = threading.RLock()

    @property
    def service_id(self) -> str:
        return f"{self.namespace}/{self.name}"

    def add_route(self, route: TrafficRoute) -> None:
        with self._lock:
            self._routes.append(route)
            self.updated_at = datetime.utcnow()

    def remove_route(self, route_id: str) -> bool:
        with self._lock:
            for i, r in enumerate(self._routes):
                if r.route_id == route_id:
                    self._routes.pop(i)
                    self.updated_at = datetime.utcnow()
                    return True
            return False

    def get_routes(self) -> List[TrafficRoute]:
        with self._lock:
            return list(self._routes)

    def set_default_destinations(
        self, destinations: List[RouteDestination]
    ) -> None:
        with self._lock:
            self._default_destinations = destinations
            self.updated_at = datetime.utcnow()

    def get_default_destinations(self) -> List[RouteDestination]:
        with self._lock:
            return list(self._default_destinations)

    def create_weighted_route(
        self,
        route_id: str,
        path: str = "/",
        stable_host: str = "",
        canary_host: str = "",
        stable_weight: float = 80.0,
        canary_weight: float = 20.0,
        stable_version: str = "stable",
        canary_version: str = "canary",
    ) -> TrafficRoute:
        """Create a weighted route splitting traffic between stable and canary."""
        route = TrafficRoute(
            route_id=route_id,
            name=f"{self.name}-{route_id}",
            host=self.hosts[0] if self.hosts else "*",
            path=path,
            path_match=RouteMatchType.PREFIX,
        )
        if stable_host:
            route.destinations.append(
                RouteDestination(
                    host=stable_host,
                    weight=stable_weight,
                    version=stable_version,
                )
            )
        if canary_host:
            route.destinations.append(
                RouteDestination(
                    host=canary_host,
                    weight=canary_weight,
                    version=canary_version,
                )
            )
        self.add_route(route)
        return route

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "namespace": self.namespace,
                "service_id": self.service_id,
                "hosts": self.hosts,
                "enabled": self.enabled,
                "metadata": self.metadata,
                "route_count": len(self._routes),
                "routes": [r.to_dict() for r in self._routes],
                "default_destinations": [
                    d.to_dict() for d in self._default_destinations
                ],
                "created_at": self.created_at.isoformat(),
                "updated_at": self.updated_at.isoformat(),
            }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "route_count": len(self._routes),
                "destination_count": len(
                    self._default_destinations
                ),
                "enabled": self.enabled,
            }