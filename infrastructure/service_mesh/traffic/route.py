"""Route definitions for ICYQuant Service Mesh Traffic Management.

Provides ``TrafficRoute`` for defining routing rules with path,
header, method, and query-based matching, plus weighted destination
targets and optional policy overrides.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RouteMatchType(str, Enum):
    """Type of route matching."""

    EXACT = "exact"
    PREFIX = "prefix"
    REGEX = "regex"
    CONTAINS = "contains"


class RouteDestination:
    """A weighted destination for a route."""

    def __init__(
        self,
        host: str,
        port: int = 80,
        weight: float = 1.0,
        version: str = "",
        subset: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.weight = weight
        self.version = version
        self.subset = subset
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "weight": self.weight,
            "version": self.version,
            "subset": self.subset,
            "metadata": self.metadata,
        }


class TrafficRoute:
    """A traffic routing rule."""

    def __init__(
        self,
        route_id: str,
        name: str,
        host: str = "*",
        path: str = "/",
        path_match: RouteMatchType = RouteMatchType.PREFIX,
        methods: Optional[List[str]] = None,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, str]] = None,
        destinations: Optional[List[RouteDestination]] = None,
        retry_policy_id: str = "",
        timeout_policy_id: str = "",
        circuit_policy_id: str = "",
        mirror_policy_id: str = "",
        rewrite: Optional[Dict[str, str]] = None,
        enabled: bool = True,
        priority: int = 100,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        self.route_id = route_id
        self.name = name
        self.host = host
        self.path = path
        self.path_match = path_match
        self.methods = methods or ["GET", "POST", "PUT", "DELETE", "PATCH"]
        self.headers = headers or {}
        self.query_params = query_params or {}
        self.destinations = destinations or []
        self.retry_policy_id = retry_policy_id
        self.timeout_policy_id = timeout_policy_id
        self.circuit_policy_id = circuit_policy_id
        self.mirror_policy_id = mirror_policy_id
        self.rewrite = rewrite or {}
        self.enabled = enabled
        self.priority = priority
        self.tags = tags or {}
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def add_destination(
        self,
        host: str,
        port: int = 80,
        weight: float = 1.0,
        version: str = "",
        subset: str = "",
    ) -> None:
        """Add a weighted destination to this route."""
        self.destinations.append(
            RouteDestination(
                host=host,
                port=port,
                weight=weight,
                version=version,
                subset=subset,
            )
        )
        self.updated_at = datetime.utcnow()

    def get_total_weight(self) -> float:
        """Get the sum of all destination weights."""
        return sum(d.weight for d in self.destinations)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route_id": self.route_id,
            "name": self.name,
            "host": self.host,
            "path": self.path,
            "path_match": self.path_match.value,
            "methods": self.methods,
            "headers": self.headers,
            "query_params": self.query_params,
            "destinations": [d.to_dict() for d in self.destinations],
            "retry_policy_id": self.retry_policy_id,
            "timeout_policy_id": self.timeout_policy_id,
            "circuit_policy_id": self.circuit_policy_id,
            "mirror_policy_id": self.mirror_policy_id,
            "rewrite": self.rewrite,
            "enabled": self.enabled,
            "priority": self.priority,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class RouteTable:
    """Thread-safe route table."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._routes: Dict[str, TrafficRoute] = {}
        self._update_count = 0

    def add_route(self, route: TrafficRoute) -> None:
        with self._lock:
            self._routes[route.route_id] = route
            self._update_count += 1

    def remove_route(self, route_id: str) -> bool:
        with self._lock:
            if route_id in self._routes:
                del self._routes[route_id]
                self._update_count += 1
                return True
            return False

    def get_route(self, route_id: str) -> Optional[TrafficRoute]:
        with self._lock:
            return self._routes.get(route_id)

    def list_routes(self) -> List[TrafficRoute]:
        with self._lock:
            return sorted(
                self._routes.values(),
                key=lambda r: r.priority,
                reverse=True,
            )

    def list_routes_dict(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in sorted(
                self._routes.values(),
                key=lambda r: r.priority,
                reverse=True,
            )]

    def clear(self) -> None:
        with self._lock:
            self._routes.clear()
            self._update_count += 1

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "route_count": len(self._routes),
                "update_count": self._update_count,
            }
