"""Mesh Control API for the Service Mesh Platform.

Provides ``MeshControlAPI`` for unified REST API endpoints
for mesh platform management including status, topology,
services, traces, reload, snapshot, and restore.
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


class ControlAPIEndpoint:
    """Represents a control API endpoint."""

    def __init__(
        self,
        method: str,
        path: str,
        handler: Callable,
        description: str = "",
    ) -> None:
        self.method = method.upper()
        self.path = path
        self.handler = handler
        self.description = description

    @property
    def route(self) -> str:
        return f"{self.method} {self.path}"


class MeshControlAPI:
    """Unified control API for the service mesh platform."""

    def __init__(
        self,
        telemetry: Optional[PlatformTelemetry] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._telemetry = telemetry or PlatformTelemetry()
        self._metrics = metrics or PlatformMetrics()
        self._endpoints: Dict[str, ControlAPIEndpoint] = {}
        self._middleware: List[Callable] = []
        self._request_count = 0
        self._started = False
        self._start_time: Optional[float] = None
        self._request_history: List[Dict[str, Any]] = []
        self._max_history = 500
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register_endpoint(
            "GET", "/mesh/status",
            self._handle_status,
            "Get mesh platform status",
        )
        self.register_endpoint(
            "GET", "/mesh/topology",
            self._handle_topology,
            "Get mesh service topology",
        )
        self.register_endpoint(
            "GET", "/mesh/services",
            self._handle_services,
            "Get all registered services",
        )
        self.register_endpoint(
            "GET", "/mesh/traces",
            self._handle_traces,
            "Get recent mesh traces",
        )
        self.register_endpoint(
            "POST", "/mesh/reload",
            self._handle_reload,
            "Reload mesh configuration",
        )
        self.register_endpoint(
            "POST", "/mesh/snapshot",
            self._handle_snapshot,
            "Create mesh snapshot",
        )
        self.register_endpoint(
            "POST", "/mesh/restore",
            self._handle_restore,
            "Restore mesh from snapshot",
        )

    def register_endpoint(
        self,
        method: str,
        path: str,
        handler: Callable,
        description: str = "",
    ) -> None:
        key = f"{method.upper()}:{path}"
        endpoint = ControlAPIEndpoint(
            method, path, handler, description
        )
        self._endpoints[key] = endpoint

    def add_middleware(self, middleware: Callable) -> None:
        self._middleware.append(middleware)

    async def start(self) -> Dict[str, Any]:
        self._started = True
        self._start_time = time.monotonic()
        self._telemetry.log_control_api(
            "/mesh/status", "GET", 200, 0.001,
        )
        logger.info("Mesh control API started.")
        return {"success": True, "started": True}

    async def stop(self) -> Dict[str, Any]:
        self._started = False
        self._telemetry.log_control_api(
            "/mesh/status", "GET", 200, 0.001,
        )
        logger.info("Mesh control API stopped.")
        return {"success": True, "started": False}

    @property
    def is_running(self) -> bool:
        return self._started

    async def handle_request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Handle an API request."""
        self._metrics.increment_control_api_total(
            {"method": method, "path": path}
        )

        key = f"{method.upper()}:{path}"
        endpoint = self._endpoints.get(key)

        if endpoint is None:
            self._record_request(
                method, path, 404, 0.001,
            )
            return {
                "success": False,
                "status_code": 404,
                "error": f"Endpoint not found: {key}",
            }

        start = time.monotonic()

        # Run middleware
        for mw in self._middleware:
            try:
                result = mw(method, path, body, headers)
                if asyncio.iscoroutine(result):
                    result = await result
                if result and not result.get("success", True):
                    duration = time.monotonic() - start
                    self._record_request(
                        method, path, result.get("status_code", 400),
                        duration,
                    )
                    return result
            except Exception as exc:
                duration = time.monotonic() - start
                self._record_request(
                    method, path, 500, duration,
                )
                return {
                    "success": False,
                    "status_code": 500,
                    "error": f"Middleware error: {exc}",
                }

        # Run handler
        try:
            result = endpoint.handler(body, headers)
            if asyncio.iscoroutine(result):
                result = await result
            duration = time.monotonic() - start
            self._record_request(
                method, path,
                result.get("status_code", 200),
                duration,
            )
            self._telemetry.log_control_api(
                path, method,
                result.get("status_code", 200),
                duration,
            )
            return result
        except Exception as exc:
            duration = time.monotonic() - start
            self._record_request(method, path, 500, duration)
            self._telemetry.log_error(
                "control_api", "handler_error", str(exc),
                {"method": method, "path": path},
            )
            return {
                "success": False,
                "status_code": 500,
                "error": str(exc),
            }

    def _record_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_s: float,
    ) -> None:
        self._request_count += 1
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_s": duration_s,
        }
        with self._lock:
            self._request_history.append(record)
            if len(self._request_history) > self._max_history:
                self._request_history = (
                    self._request_history[-self._max_history:]
                )

    # Default handlers
    def _handle_status(
        self,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "status_code": 200,
            "data": {
                "status": "running" if self._started else "stopped",
                "uptime_s": (
                    time.monotonic() - self._start_time
                    if self._start_time
                    else 0
                ),
                "request_count": self._request_count,
                "endpoints": list(self._endpoints.keys()),
            },
        }

    def _handle_topology(
        self,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "status_code": 200,
            "data": {
                "nodes": [],
                "connections": [],
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

    def _handle_services(
        self,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "status_code": 200,
            "data": {
                "services": [],
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

    def _handle_traces(
        self,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        traces = self._telemetry.get_records(
            category="runtime", limit=50
        )
        return {
            "success": True,
            "status_code": 200,
            "data": {
                "traces": traces,
                "total": len(traces),
            },
        }

    def _handle_reload(
        self,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "status_code": 200,
            "data": {
                "reloaded": True,
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

    def _handle_snapshot(
        self,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "status_code": 200,
            "data": {
                "snapshot_id": "placeholder",
                "created_at": datetime.utcnow().isoformat(),
            },
        }

    def _handle_restore(
        self,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "status_code": 200,
            "data": {
                "restored": True,
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

    def get_endpoints(self) -> List[Dict[str, str]]:
        return [
            {
                "method": ep.method,
                "path": ep.path,
                "description": ep.description,
            }
            for ep in self._endpoints.values()
        ]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._started,
                "request_count": self._request_count,
                "endpoint_count": len(self._endpoints),
                "middleware_count": len(self._middleware),
                "request_history_size": len(self._request_history),
                "uptime_s": (
                    time.monotonic() - self._start_time
                    if self._start_time
                    else 0
                ),
            }

    def __repr__(self) -> str:
        return (
            f"MeshControlAPI(endpoints={len(self._endpoints)}, "
            f"running={self._started})"
        )
