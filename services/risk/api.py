"""
Risk API — Unified REST API for the Risk Management Platform.

Provides endpoints for risk evaluation, policy management,
status monitoring, profile access, and runtime inspection.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class APIResponse:
    """Standardized API response."""
    success: bool = True
    data: Any = None
    error: Optional[str] = None
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: Optional[str] = None


class RiskAPI:
    """
    Unified REST API for the Risk Management Platform.

    Endpoints:
        POST /risk/evaluate   — Submit a risk evaluation
        POST /risk/policy     — Manage risk policies
        GET  /risk/status     — Get risk platform status
        GET  /risk/profile    — Get risk profile
        GET  /risk/runtime    — Get runtime information
        GET  /risk/health     — Health check

    Usage::

        api = RiskAPI(control_plane=cp, risk_engine=engine)
        await api.initialize()
        response = await api.handle("POST", "/risk/evaluate", {"strategy_id": "s1"})
    """

    def __init__(
        self,
        control_plane: Any = None,
        risk_engine: Any = None,
    ) -> None:
        self._control_plane = control_plane
        self._risk_engine = risk_engine
        self._routes: dict[str, Callable] = {}
        self._request_count: int = 0

    async def initialize(self) -> None:
        """Initialize the API and register routes."""
        self._register_routes()
        logger.info("RiskAPI initialized.")

    async def stop(self) -> None:
        """Stop the API."""
        logger.info("RiskAPI stopped.")

    # ---- Route Registration ----

    def _register_routes(self) -> None:
        """Register all API routes."""
        self._routes = {
            "POST:/risk/evaluate": self._handle_evaluate,
            "POST:/risk/policy": self._handle_policy,
            "GET:/risk/status": self._handle_status,
            "GET:/risk/profile": self._handle_profile,
            "GET:/risk/runtime": self._handle_runtime,
            "GET:/risk/health": self._handle_health,
            "POST:/risk/policy/create": self._handle_policy_create,
            "PUT:/risk/policy/update": self._handle_policy_update,
            "DELETE:/risk/policy/remove": self._handle_policy_remove,
        }

    # ---- Request Handling ----

    async def handle(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> APIResponse:
        """Handle an API request."""
        self._request_count += 1
        key = f"{method.upper()}:{path}"

        handler = self._routes.get(key)
        if not handler:
            return APIResponse(success=False, error=f"Route not found: {method} {path}")

        try:
            return await handler(params or {})
        except Exception as e:
            logger.error(f"API error {method} {path}: {e}")
            return APIResponse(success=False, error=str(e))

    # ---- Route Handlers ----

    async def _handle_evaluate(self, params: dict) -> APIResponse:
        if self._control_plane:
            from services.risk.control_plane import ControlCommand
            result = await self._control_plane.execute(ControlCommand.EVALUATE, params)
            return APIResponse(success=result.success, data=result.details,
                               message=result.message)
        return APIResponse(data={"status": "simulated"})

    async def _handle_policy(self, params: dict) -> APIResponse:
        return APIResponse(data={"policies": [], "method": "POST"})

    async def _handle_status(self, params: dict) -> APIResponse:
        if self._risk_engine:
            health = await self._risk_engine.health_check()
            return APIResponse(data=health)
        return APIResponse(data={"status": "ok", "platform": "risk"})

    async def _handle_profile(self, params: dict) -> APIResponse:
        profile_id = params.get("profile_id", "")
        return APIResponse(data={"profile_id": profile_id, "risk_level": "moderate"})

    async def _handle_runtime(self, params: dict) -> APIResponse:
        if self._risk_engine and self._risk_engine.runtime:
            health = await self._risk_engine.runtime.health_check()
            return APIResponse(data=health)
        return APIResponse(data={"status": "running"})

    async def _handle_health(self, params: dict) -> APIResponse:
        return APIResponse(data={"status": "healthy", "platform": "risk",
                                 "uptime": "operational"})

    async def _handle_policy_create(self, params: dict) -> APIResponse:
        return APIResponse(success=True, message=f"Policy created: {params.get('policy_id', 'unknown')}")

    async def _handle_policy_update(self, params: dict) -> APIResponse:
        return APIResponse(success=True, message=f"Policy updated: {params.get('policy_id', 'unknown')}")

    async def _handle_policy_remove(self, params: dict) -> APIResponse:
        return APIResponse(success=True, message=f"Policy removed: {params.get('policy_id', 'unknown')}")

    async def list_routes(self) -> list[dict[str, str]]:
        """List all registered API routes."""
        return [{"method": k.split(":")[0], "path": k.split(":")[1]} for k in self._routes.keys()]

    async def health_check(self) -> dict[str, Any]:
        """Check API health."""
        return {
            "status": "healthy",
            "routes": len(self._routes),
            "requests_served": self._request_count,
        }
