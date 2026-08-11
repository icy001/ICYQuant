"""
REST API — HTTP REST endpoints for the Strategy Platform.

Provides RESTful API for strategy registration, deployment,
lifecycle management, and platform monitoring.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class HTTPMethod(str, Enum):
    """HTTP methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


@dataclass
class RESTEndpoint:
    """Definition of a REST API endpoint."""
    path: str
    method: HTTPMethod
    handler: Callable
    description: str = ""
    auth_required: bool = True
    rate_limit: Optional[int] = None  # requests per minute
    tags: list[str] = field(default_factory=list)


@dataclass
class RESTResponse:
    """Standardized REST API response."""
    status_code: int = 200
    success: bool = True
    data: Any = None
    error: Optional[str] = None
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: Optional[str] = None


class StrategyRESTAPI:
    """
    RESTful API for the Strategy Platform.

    Exposes strategy management, deployment, lifecycle control,
    and platform health through standard HTTP endpoints.

    Endpoints::

        POST   /api/v1/strategy/register
        POST   /api/v1/strategy/deploy
        POST   /api/v1/strategy/{id}/start
        POST   /api/v1/strategy/{id}/pause
        POST   /api/v1/strategy/{id}/resume
        POST   /api/v1/strategy/{id}/stop
        GET    /api/v1/strategy/{id}/status
        GET    /api/v1/strategy/{id}/runtime
        GET    /api/v1/strategy/catalog
        GET    /api/v1/platform/health
        GET    /api/v1/platform/metrics
        GET    /api/v1/platform/audit
    """

    API_PREFIX = "/api/v1"

    def __init__(
        self,
        control_plane: Any = None,
        gateway: Any = None,
        catalog: Any = None,
        audit_center: Any = None,
    ) -> None:
        self._control_plane = control_plane
        self._gateway = gateway
        self._catalog = catalog
        self._audit_center = audit_center
        self._endpoints: dict[str, RESTEndpoint] = {}
        self._request_count: int = 0
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the REST API and register endpoints."""
        self._register_endpoints()
        self._initialized = True
        logger.info("StrategyRESTAPI initialized.")

    async def stop(self) -> None:
        """Stop the REST API."""
        self._initialized = False
        logger.info("StrategyRESTAPI stopped.")

    # ---- Endpoint Registration ----

    def _register_endpoints(self) -> None:
        """Register all REST API endpoints."""
        self._add_endpoint(RESTEndpoint(
            path=f"{self.API_PREFIX}/strategy/register",
            method=HTTPMethod.POST,
            handler=self._register_strategy,
            description="Register a new strategy",
            tags=["strategy"],
        ))
        self._add_endpoint(RESTEndpoint(
            path=f"{self.API_PREFIX}/strategy/deploy",
            method=HTTPMethod.POST,
            handler=self._deploy_strategy,
            description="Deploy a strategy version",
            tags=["strategy", "deployment"],
        ))
        self._add_endpoint(RESTEndpoint(
            path=f"{self.API_PREFIX}/strategy/release",
            method=HTTPMethod.POST,
            handler=self._release_strategy,
            description="Release a strategy version",
            tags=["strategy", "release"],
        ))
        self._add_endpoint(RESTEndpoint(
            path=f"{self.API_PREFIX}/strategy/{{id}}/start",
            method=HTTPMethod.POST,
            handler=self._start_strategy,
            description="Start a strategy",
            tags=["strategy", "lifecycle"],
        ))
        self._add_endpoint(RESTEndpoint(
            path=f"{self.API_PREFIX}/strategy/{{id}}/pause",
            method=HTTPMethod.POST,
            handler=self._pause_strategy,
            description="Pause a strategy",
            tags=["strategy", "lifecycle"],
        ))
        self._add_endpoint(RESTEndpoint(
            path=f"{self.API_PREFIX}/strategy/{{id}}/resume",
            method=HTTPMethod.POST,
            handler=self._resume_strategy,
            description="Resume a strategy",
            tags=["strategy", "lifecycle"],
        ))
        self._add_endpoint(RESTEndpoint(
            path=f"{self.API_PREFIX}/strategy/{{id}}/stop",
            method=HTTPMethod.POST,
            handler=self._stop_strategy,
            description="Stop a strategy",
            tags=["strategy", "lifecycle"],
        ))
        self._add_endpoint(RESTEndpoint(
            path=f"{self.API_PREFIX}/strategy/{{id}}/status",
            method=HTTPMethod.GET,
            handler=self._get_strategy_status,
            description="Get strategy status",
            tags=["strategy"],
        ))
        self._add_endpoint(RESTEndpoint(
            path=f"{self.API_PREFIX}/strategy/{{id}}/runtime",
            method=HTTPMethod.GET,
            handler=self._get_strategy_runtime,
            description="Get strategy runtime info",
            tags=["strategy"],
        ))
        self._add_endpoint(RESTEndpoint(
            path=f"{self.API_PREFIX}/strategy/catalog",
            method=HTTPMethod.GET,
            handler=self._get_catalog,
            description="Get strategy catalog",
            tags=["strategy", "catalog"],
        ))
        self._add_endpoint(RESTEndpoint(
            path=f"{self.API_PREFIX}/platform/health",
            method=HTTPMethod.GET,
            handler=self._get_health,
            description="Get platform health",
            tags=["platform"],
            auth_required=False,
        ))
        self._add_endpoint(RESTEndpoint(
            path=f"{self.API_PREFIX}/platform/metrics",
            method=HTTPMethod.GET,
            handler=self._get_metrics,
            description="Get platform metrics",
            tags=["platform"],
        ))
        self._add_endpoint(RESTEndpoint(
            path=f"{self.API_PREFIX}/platform/audit",
            method=HTTPMethod.GET,
            handler=self._get_audit,
            description="Get audit records",
            tags=["platform", "audit"],
        ))

    def _add_endpoint(self, endpoint: RESTEndpoint) -> None:
        key = f"{endpoint.method.value}:{endpoint.path}"
        self._endpoints[key] = endpoint

    # ---- Endpoint Handlers ----

    async def _register_strategy(self, params: dict) -> RESTResponse:
        from services.strategy.platform.control_plane import ControlCommand
        if self._control_plane:
            result = await self._control_plane.execute_command(
                params.get("strategy_id", ""),
                ControlCommand.REGISTER,
                params,
            )
            return RESTResponse(success=result.success, data={"message": result.message})
        return RESTResponse(success=False, error="Control plane not available")

    async def _deploy_strategy(self, params: dict) -> RESTResponse:
        from services.strategy.platform.control_plane import ControlCommand
        if self._control_plane:
            result = await self._control_plane.execute_command(
                params.get("strategy_id", ""),
                ControlCommand.DEPLOY,
                params,
            )
            return RESTResponse(success=result.success, data={"message": result.message})
        return RESTResponse(success=False, error="Control plane not available")

    async def _release_strategy(self, params: dict) -> RESTResponse:
        return RESTResponse(data={"message": "Release endpoint"})

    async def _start_strategy(self, params: dict) -> RESTResponse:
        from services.strategy.platform.control_plane import ControlCommand
        strategy_id = params.get("id", "")
        if self._control_plane:
            result = await self._control_plane.execute_command(strategy_id, ControlCommand.START, params)
            return RESTResponse(success=result.success, data={"message": result.message})
        return RESTResponse(success=False, error="Control plane not available")

    async def _pause_strategy(self, params: dict) -> RESTResponse:
        from services.strategy.platform.control_plane import ControlCommand
        strategy_id = params.get("id", "")
        if self._control_plane:
            result = await self._control_plane.execute_command(strategy_id, ControlCommand.PAUSE, params)
            return RESTResponse(success=result.success, data={"message": result.message})
        return RESTResponse(success=False, error="Control plane not available")

    async def _resume_strategy(self, params: dict) -> RESTResponse:
        from services.strategy.platform.control_plane import ControlCommand
        strategy_id = params.get("id", "")
        if self._control_plane:
            result = await self._control_plane.execute_command(strategy_id, ControlCommand.RESUME, params)
            return RESTResponse(success=result.success, data={"message": result.message})
        return RESTResponse(success=False, error="Control plane not available")

    async def _stop_strategy(self, params: dict) -> RESTResponse:
        from services.strategy.platform.control_plane import ControlCommand
        strategy_id = params.get("id", "")
        if self._control_plane:
            result = await self._control_plane.execute_command(strategy_id, ControlCommand.STOP, params)
            return RESTResponse(success=result.success, data={"message": result.message})
        return RESTResponse(success=False, error="Control plane not available")

    async def _get_strategy_status(self, params: dict) -> RESTResponse:
        strategy_id = params.get("id", "")
        if self._control_plane:
            reg = await self._control_plane.get_registration(strategy_id)
            if reg:
                return RESTResponse(data={"strategy_id": reg.strategy_id, "status": reg.status, "version": reg.version})
            return RESTResponse(success=False, error=f"Strategy not found: {strategy_id}", status_code=404)
        return RESTResponse(success=False, error="Control plane not available")

    async def _get_strategy_runtime(self, params: dict) -> RESTResponse:
        return RESTResponse(data={"runtime": "strategy_runtime_info"})

    async def _get_catalog(self, params: dict) -> RESTResponse:
        if self._catalog:
            entries = await self._catalog.list_all()
            return RESTResponse(data={"entries": [{"id": e.strategy_id, "name": e.name, "status": e.status.value} for e in entries]})
        return RESTResponse(data={"entries": []})

    async def _get_health(self, params: dict) -> RESTResponse:
        return RESTResponse(data={"status": "healthy", "platform": "operational"})

    async def _get_metrics(self, params: dict) -> RESTResponse:
        return RESTResponse(data={"metrics": "platform_metrics"})

    async def _get_audit(self, params: dict) -> RESTResponse:
        if self._audit_center:
            records = await self._audit_center.get_recent(limit=int(params.get("limit", 100)))
            return RESTResponse(data={"records": [{"id": r.record_id, "category": str(r.category), "message": r.message, "timestamp": r.timestamp.isoformat()} for r in records]})
        return RESTResponse(data={"records": []})

    # ---- API Methods ----

    async def handle_request(
        self,
        method: HTTPMethod,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> RESTResponse:
        """Handle an incoming REST API request."""
        self._request_count += 1

        # Find matching endpoint
        key = f"{method.value}:{path}"
        endpoint = self._endpoints.get(key)

        if not endpoint:
            # Try path parameter matching
            endpoint = self._match_path(method, path)

        if not endpoint:
            return RESTResponse(
                status_code=404,
                success=False,
                error=f"Endpoint not found: {method.value} {path}",
            )

        try:
            return await endpoint.handler(params or {})
        except Exception as e:
            logger.error(f"API error: {method.value} {path}: {e}")
            return RESTResponse(
                status_code=500,
                success=False,
                error=str(e),
            )

    async def list_endpoints(self) -> list[dict[str, Any]]:
        """List all registered endpoints."""
        return [
            {
                "path": ep.path,
                "method": ep.method.value,
                "description": ep.description,
                "auth_required": ep.auth_required,
                "tags": ep.tags,
            }
            for ep in self._endpoints.values()
        ]

    async def health_check(self) -> dict[str, Any]:
        """Check API health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "endpoints": len(self._endpoints),
            "requests_served": self._request_count,
        }

    # ---- Internal ----

    def _match_path(self, method: HTTPMethod, path: str) -> Optional[RESTEndpoint]:
        """Match a request path with path parameters."""
        for key, endpoint in self._endpoints.items():
            ep_method, ep_path = key.split(":", 1)
            if ep_method != method.value:
                continue
            # Simple path parameter matching
            if "{id}" in ep_path:
                parts = ep_path.split("/")
                req_parts = path.split("/")
                if len(parts) != len(req_parts):
                    continue
                match = True
                for i, part in enumerate(parts):
                    if part != req_parts[i] and "{" not in part:
                        match = False
                        break
                if match:
                    return endpoint
        return None
