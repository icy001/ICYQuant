"""Unified API for ICYQuant Service Mesh observability.

Provides ``ObservabilityAPI`` for serving REST-style endpoints:
GET /mesh/overview, GET /mesh/traces, GET /mesh/policies,
GET /mesh/services, GET /mesh/slo.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from .dashboard import DashboardProvider, DashboardView

logger = logging.getLogger(__name__)


class APIRoute:
    """A single API route definition."""

    def __init__(
        self,
        method: str,
        path: str,
        handler: Callable[..., Dict[str, Any]],
        description: str = "",
    ) -> None:
        self.method = method.upper()
        self.path = path
        self.handler = handler
        self.description = description

    def matches(self, method: str, path: str) -> bool:
        return self.method == method.upper() and self.path == path

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "path": self.path,
            "description": self.description,
        }


class APIResponse:
    """Standard API response."""

    def __init__(
        self,
        status: int = 200,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        self.status = status
        self.data = data or {}
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"status": self.status}
        if self.error:
            result["error"] = self.error
        else:
            result["data"] = self.data
        return result


class ObservabilityAPI:
    """Unified observability REST API."""

    def __init__(
        self,
        dashboard: Optional[DashboardProvider] = None,
    ) -> None:
        self._dashboard = dashboard or DashboardProvider()
        self._lock = threading.RLock()
        self._routes: List[APIRoute] = []
        self._request_count = 0
        self._started = False
        self._register_default_routes()

    @property
    def dashboard(self) -> DashboardProvider:
        return self._dashboard

    @property
    def is_running(self) -> bool:
        return self._started

    def start(self) -> None:
        self._dashboard.start()
        self._started = True
        logger.info("Observability API started")

    def stop(self) -> None:
        self._dashboard.stop()
        self._started = False
        logger.info("Observability API stopped")

    def _register_default_routes(self) -> None:
        routes = [
            APIRoute("GET", "/mesh/overview", self.handle_overview, "Mesh overview"),
            APIRoute("GET", "/mesh/traces", self.handle_traces, "List traces"),
            APIRoute("GET", "/mesh/policies", self.handle_policies, "List policies"),
            APIRoute("GET", "/mesh/services", self.handle_services, "List services"),
            APIRoute("GET", "/mesh/slo", self.handle_slo, "SLO status"),
            APIRoute("GET", "/mesh/topology", self.handle_topology, "Mesh topology"),
            APIRoute("GET", "/mesh/health", self.handle_health, "Mesh health"),
            APIRoute("GET", "/mesh/anomalies", self.handle_anomalies, "List anomalies"),
            APIRoute("GET", "/mesh/analysis", self.handle_analysis, "Runtime analysis"),
            APIRoute("GET", "/mesh/metrics", self.handle_metrics, "Mesh metrics"),
        ]
        for route in routes:
            self._routes.append(route)

    def add_route(self, route: APIRoute) -> None:
        with self._lock:
            self._routes.append(route)

    def handle(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> APIResponse:
        with self._lock:
            self._request_count += 1
            routes = list(self._routes)

        for route in routes:
            if route.matches(method, path):
                try:
                    start = time.monotonic()
                    data = route.handler(**(params or {}))
                    duration = time.monotonic() - start
                    data["_meta"] = {
                        "method": method,
                        "path": path,
                        "duration_s": duration,
                    }
                    return APIResponse(200, data)
                except Exception as exc:
                    logger.error("API handler error: %s", exc)
                    return APIResponse(500, error=str(exc))

        return APIResponse(404, error=f"Route not found: {method} {path}")

    def handle_overview(self, **kwargs: Any) -> Dict[str, Any]:
        return self._dashboard.get_overview()

    def handle_traces(self, limit: int = 20, **kwargs: Any) -> Dict[str, Any]:
        return self._dashboard.get_traces(limit=limit)

    def handle_policies(self, **kwargs: Any) -> Dict[str, Any]:
        return self._dashboard.get_policies()

    def handle_services(self, **kwargs: Any) -> Dict[str, Any]:
        return {
            "services": [],
            "count": 0,
        }

    def handle_slo(self, **kwargs: Any) -> Dict[str, Any]:
        return self._dashboard.get_slo()

    def handle_topology(self, **kwargs: Any) -> Dict[str, Any]:
        return self._dashboard.get_topology()

    def handle_health(self, **kwargs: Any) -> Dict[str, Any]:
        return self._dashboard.get_health()

    def handle_anomalies(self, limit: int = 50, **kwargs: Any) -> Dict[str, Any]:
        return self._dashboard.get_anomalies(limit=limit)

    def handle_analysis(self, **kwargs: Any) -> Dict[str, Any]:
        return self._dashboard.get_analysis()

    def handle_metrics(self, **kwargs: Any) -> Dict[str, Any]:
        return self._dashboard.get_traffic()

    def list_routes(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._routes]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._started,
                "route_count": len(self._routes),
                "request_count": self._request_count,
                "dashboard": self._dashboard.get_stats(),
            }
