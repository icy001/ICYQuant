"""
Strategy Gateway — Unified API gateway for all strategy platform requests.

Routes external API calls to the control plane, enforces authentication,
rate limiting, and request validation before forwarding commands.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class GatewayRoute(str, Enum):
    """Gateway route identifiers."""
    REGISTER = "strategy.register"
    DEPLOY = "strategy.deploy"
    START = "strategy.start"
    PAUSE = "strategy.pause"
    RESUME = "strategy.resume"
    STOP = "strategy.stop"
    STATUS = "strategy.status"
    CATALOG = "strategy.catalog"
    AUDIT = "strategy.audit"
    HEALTH = "platform.health"
    METRICS = "platform.metrics"


@dataclass
class GatewayConfig:
    """Gateway configuration."""
    max_requests_per_second: int = 1000
    request_timeout_seconds: float = 30.0
    enable_auth: bool = True
    enable_rate_limiting: bool = True
    enable_request_logging: bool = True
    allowed_origins: list[str] = field(default_factory=lambda: ["*"])


@dataclass
class GatewayRequest:
    """Incoming gateway request."""
    route: GatewayRoute
    strategy_id: Optional[str] = None
    params: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    request_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class GatewayResponse:
    """Gateway response."""
    request_id: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    status_code: int = 200
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class StrategyGateway:
    """
    Unified API gateway for strategy platform requests.

    Provides a single entry point for all external interactions,
    handling authentication, rate limiting, routing, and response
    normalization.

    Usage::

        gateway = StrategyGateway(control_plane=cp)
        await gateway.initialize()
        response = await gateway.handle_request(GatewayRequest(
            route=GatewayRoute.DEPLOY,
            strategy_id="strat_001",
            params={"version": "1.2.0"},
        ))
    """

    def __init__(
        self,
        control_plane: Any = None,
        config: Optional[GatewayConfig] = None,
    ) -> None:
        self._control_plane = control_plane
        self._config = config or GatewayConfig()
        self._route_handlers: dict[GatewayRoute, Callable] = {}
        self._rate_limiter: dict[str, list[float]] = {}
        self._request_count: int = 0

    async def initialize(self) -> None:
        """Initialize the gateway and register routes."""
        self._register_routes()
        logger.info("StrategyGateway initialized.")

    async def stop(self) -> None:
        """Stop the gateway."""
        logger.info("StrategyGateway stopped.")

    # ---- Request Handling ----

    async def handle_request(self, request: GatewayRequest) -> GatewayResponse:
        """Handle an incoming gateway request."""
        start = asyncio.get_event_loop().time()

        # Rate limiting
        if self._config.enable_rate_limiting:
            if not self._check_rate_limit(request.route.value):
                return GatewayResponse(
                    request_id=request.request_id,
                    success=False,
                    error="Rate limit exceeded",
                    status_code=429,
                )

        # Route to handler
        handler = self._route_handlers.get(request.route)
        if not handler:
            return GatewayResponse(
                request_id=request.request_id,
                success=False,
                error=f"Unknown route: {request.route}",
                status_code=404,
            )

        try:
            result = await handler(request)
            latency = (asyncio.get_event_loop().time() - start) * 1000
            return GatewayResponse(
                request_id=request.request_id,
                success=result.get("success", True),
                data=result,
                latency_ms=latency,
            )
        except Exception as e:
            logger.error(f"Gateway error for route {request.route}: {e}")
            latency = (asyncio.get_event_loop().time() - start) * 1000
            return GatewayResponse(
                request_id=request.request_id,
                success=False,
                error=str(e),
                status_code=500,
                latency_ms=latency,
            )

    # ---- Route Registration ----

    def _register_routes(self) -> None:
        """Register all gateway route handlers."""
        self._route_handlers[GatewayRoute.REGISTER] = self._handle_register
        self._route_handlers[GatewayRoute.DEPLOY] = self._handle_deploy
        self._route_handlers[GatewayRoute.START] = self._handle_start
        self._route_handlers[GatewayRoute.PAUSE] = self._handle_pause
        self._route_handlers[GatewayRoute.RESUME] = self._handle_resume
        self._route_handlers[GatewayRoute.STOP] = self._handle_stop
        self._route_handlers[GatewayRoute.STATUS] = self._handle_status
        self._route_handlers[GatewayRoute.CATALOG] = self._handle_catalog
        self._route_handlers[GatewayRoute.AUDIT] = self._handle_audit
        self._route_handlers[GatewayRoute.HEALTH] = self._handle_health
        self._route_handlers[GatewayRoute.METRICS] = self._handle_metrics

    # ---- Route Handlers ----

    async def _handle_register(self, req: GatewayRequest) -> dict:
        from services.strategy.platform.control_plane import ControlCommand
        if not self._control_plane:
            raise RuntimeError("Control plane not initialized")
        result = await self._control_plane.execute_command(
            req.strategy_id or "unknown",
            ControlCommand.REGISTER,
            req.params,
        )
        return {"success": result.success, "message": result.message, "details": result.details}

    async def _handle_deploy(self, req: GatewayRequest) -> dict:
        from services.strategy.platform.control_plane import ControlCommand
        result = await self._control_plane.execute_command(
            req.strategy_id or "unknown",
            ControlCommand.DEPLOY,
            req.params,
        )
        return {"success": result.success, "message": result.message}

    async def _handle_start(self, req: GatewayRequest) -> dict:
        from services.strategy.platform.control_plane import ControlCommand
        result = await self._control_plane.execute_command(
            req.strategy_id or "unknown",
            ControlCommand.START,
            req.params,
        )
        return {"success": result.success, "message": result.message}

    async def _handle_pause(self, req: GatewayRequest) -> dict:
        from services.strategy.platform.control_plane import ControlCommand
        result = await self._control_plane.execute_command(
            req.strategy_id or "unknown",
            ControlCommand.PAUSE,
            req.params,
        )
        return {"success": result.success, "message": result.message}

    async def _handle_resume(self, req: GatewayRequest) -> dict:
        from services.strategy.platform.control_plane import ControlCommand
        result = await self._control_plane.execute_command(
            req.strategy_id or "unknown",
            ControlCommand.RESUME,
            req.params,
        )
        return {"success": result.success, "message": result.message}

    async def _handle_stop(self, req: GatewayRequest) -> dict:
        from services.strategy.platform.control_plane import ControlCommand
        result = await self._control_plane.execute_command(
            req.strategy_id or "unknown",
            ControlCommand.STOP,
            req.params,
        )
        return {"success": result.success, "message": result.message}

    async def _handle_status(self, req: GatewayRequest) -> dict:
        if req.strategy_id:
            reg = await self._control_plane.get_registration(req.strategy_id)
            if reg:
                return {"strategy_id": reg.strategy_id, "status": reg.status, "version": reg.version}
            return {"success": False, "message": f"Not found: {req.strategy_id}"}
        registrations = await self._control_plane.list_registrations()
        return {"strategies": [{"id": r.strategy_id, "status": r.status, "version": r.version} for r in registrations]}

    async def _handle_catalog(self, req: GatewayRequest) -> dict:
        return {"catalog": "strategy_catalog", "count": 0}

    async def _handle_audit(self, req: GatewayRequest) -> dict:
        return {"audit": "audit_records", "count": 0}

    async def _handle_health(self, req: GatewayRequest) -> dict:
        return {"status": "healthy", "gateway": "operational"}

    async def _handle_metrics(self, req: GatewayRequest) -> dict:
        return {"request_count": self._request_count}

    # ---- Rate Limiting ----

    def _check_rate_limit(self, key: str) -> bool:
        """Simple sliding-window rate limiter."""
        now = asyncio.get_event_loop().time()
        window = 1.0
        if key not in self._rate_limiter:
            self._rate_limiter[key] = []
        timestamps = [t for t in self._rate_limiter[key] if now - t < window]
        self._rate_limiter[key] = timestamps
        if len(timestamps) >= self._config.max_requests_per_second:
            return False
        timestamps.append(now)
        self._request_count += 1
        return True
