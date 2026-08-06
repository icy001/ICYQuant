"""Scheduler Gateway — unified API gateway for the scheduler platform.

The :class:`SchedulerGateway` provides a single entry point for all
scheduler interactions: REST API routing, gRPC bridge, and internal
service calls. It sits between external consumers and the scheduler
engine, handling auth, rate-limiting, and request transformation.

Architecture::

    External Clients (Dashboard / SDK / CLI)
              │
       SchedulerGateway
              │
    ┌─────────┼─────────┐
    REST API   gRPC    Internal
    └─────────┼─────────┘
       SchedulerEngine
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GatewayMode(enum.Enum):
    """Gateway operational modes."""

    REST = "rest"
    GRPC = "grpc"
    INTERNAL = "internal"
    HYBRID = "hybrid"


class SchedulerGateway:
    """Unified API gateway for the scheduler platform.

    Responsibilities:
    * Route external requests to the scheduler engine
    * Apply authentication and authorization
    * Rate limiting and throttling
    * Request/response transformation
    * API versioning

    Usage::

        gateway = SchedulerGateway(scheduler_engine=engine, mode=GatewayMode.REST)
        await gateway.start()
        response = await gateway.handle_request("/scheduler/jobs", method="GET")
    """

    def __init__(
        self,
        scheduler_engine: Any = None,
        mode: GatewayMode = GatewayMode.HYBRID,
    ) -> None:
        self._engine = scheduler_engine
        self._mode = mode
        self._lock = threading.Lock()
        self._started = False
        self._started_at: Optional[datetime] = None
        self._request_count: int = 0
        self._error_count: int = 0
        self._routes: Dict[str, Any] = {}
        self._middleware: List[Any] = []
        self._rate_limiter: Optional[Any] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def mode(self) -> GatewayMode:
        return self._mode

    @property
    def started(self) -> bool:
        return self._started

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def error_count(self) -> int:
        return self._error_count

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the gateway, binding routes and middleware."""
        self._started_at = datetime.now(timezone.utc)
        self._register_routes()
        self._started = True
        logger.info("SchedulerGateway: started in %s mode", self._mode.value)

    async def stop(self) -> None:
        """Stop the gateway gracefully."""
        self._started = False
        logger.info("SchedulerGateway: stopped")

    # ------------------------------------------------------------------
    # Route Registration
    # ------------------------------------------------------------------

    def register_route(self, path: str, handler: Any, methods: Optional[List[str]] = None) -> None:
        """Register a route handler."""
        self._routes[path] = {"handler": handler, "methods": methods or ["GET"]}
        logger.debug("SchedulerGateway: registered route %s", path)

    def register_middleware(self, middleware: Any) -> None:
        """Register a middleware handler (auth, logging, rate-limit)."""
        self._middleware.append(middleware)

    # ------------------------------------------------------------------
    # Request Handling
    # ------------------------------------------------------------------

    async def handle_request(
        self,
        path: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Handle an incoming API request.

        Pipeline:
        1. Rate limit check
        2. Middleware chain (auth → logging → transform)
        3. Route dispatch
        4. Response formatting
        """
        self._request_count += 1

        # Rate limiting
        if self._rate_limiter and hasattr(self._rate_limiter, "allow"):
            if not await self._rate_limiter.allow(path):
                return {"error": "rate_limit_exceeded", "status": 429}

        # Middleware
        request = {"path": path, "method": method, "params": params or {}, "body": body or {}}
        for mw in self._middleware:
            try:
                if hasattr(mw, "process"):
                    request = await mw.process(request) if asyncio.iscoroutinefunction(mw.process) else mw.process(request)
            except Exception as exc:
                logger.warning("SchedulerGateway: middleware error: %s", exc)

        # Route
        route = self._routes.get(path)
        if not route:
            self._error_count += 1
            return {"error": "not_found", "status": 404}

        if method not in route["methods"]:
            self._error_count += 1
            return {"error": "method_not_allowed", "status": 405}

        try:
            result = route["handler"](request)
            if asyncio.iscoroutine(result):
                result = await result
            return {"data": result, "status": 200}
        except Exception as exc:
            self._error_count += 1
            logger.error("SchedulerGateway: handler error for %s: %s", path, exc)
            return {"error": str(exc), "status": 500}

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _register_routes(self) -> None:
        """Register default scheduler API routes."""
        # These are registered as stubs; actual handlers are injected by DashboardAPI
        pass
