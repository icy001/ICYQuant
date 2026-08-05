"""Route matching engine for ICYQuant Service Mesh.

Provides ``RouteMatcher`` for evaluating incoming requests against
registered routes using path, header, method, and query parameter
matching strategies.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any, Dict, List, Optional, Tuple

from .route import RouteMatchType, RouteTable, TrafficRoute

logger = logging.getLogger(__name__)


class RouteMatcher:
    """Matches incoming requests against route rules."""

    def __init__(self, route_table: Optional[RouteTable] = None) -> None:
        self._lock = threading.RLock()
        self._route_table = route_table or RouteTable()
        self._match_count = 0
        self._miss_count = 0

    @property
    def route_table(self) -> RouteTable:
        return self._route_table

    def set_route_table(self, route_table: RouteTable) -> None:
        with self._lock:
            self._route_table = route_table

    def match(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, str]] = None,
        host: str = "",
    ) -> Optional[TrafficRoute]:
        """Find the best matching route for a request."""
        with self._lock:
            routes = self._route_table.list_routes()

        headers = headers or {}
        query_params = query_params or {}

        for route in routes:
            if not route.enabled:
                continue

            if not self._match_host(route, host):
                continue

            if not self._match_method(route, method):
                continue

            if not self._match_path(route, path):
                continue

            if not self._match_headers(route, headers):
                continue

            if not self._match_query(route, query_params):
                continue

            self._match_count += 1
            return route

        self._miss_count += 1
        return None

    def _match_host(self, route: TrafficRoute, host: str) -> bool:
        if route.host == "*" or not route.host:
            return True
        return host == route.host

    def _match_method(
        self, route: TrafficRoute, method: str
    ) -> bool:
        if not route.methods:
            return True
        return method.upper() in [m.upper() for m in route.methods]

    def _match_path(
        self, route: TrafficRoute, path: str
    ) -> bool:
        if not route.path or route.path == "/":
            return True

        match_type = route.path_match
        pattern = route.path

        if match_type == RouteMatchType.EXACT:
            return path == pattern
        elif match_type == RouteMatchType.PREFIX:
            return path.startswith(pattern)
        elif match_type == RouteMatchType.CONTAINS:
            return pattern in path
        elif match_type == RouteMatchType.REGEX:
            try:
                return bool(re.search(pattern, path))
            except re.error:
                return False
        return False

    def _match_headers(
        self, route: TrafficRoute, headers: Dict[str, str]
    ) -> bool:
        if not route.headers:
            return True
        for key, value in route.headers.items():
            header_val = headers.get(key, "")
            if header_val != value:
                return False
        return True

    def _match_query(
        self,
        route: TrafficRoute,
        query_params: Dict[str, str],
    ) -> bool:
        if not route.query_params:
            return True
        for key, value in route.query_params.items():
            param_val = query_params.get(key, "")
            if param_val != value:
                return False
        return True

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._match_count + self._miss_count
            hit_rate = (
                self._match_count / total if total > 0 else 0.0
            )
            return {
                "match_count": self._match_count,
                "miss_count": self._miss_count,
                "hit_rate": hit_rate,
                "total_evaluated": total,
            }
