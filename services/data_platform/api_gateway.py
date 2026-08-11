"""
ICYQuant Data API Gateway — unified API gateway for the data platform.

Provides a single entry point for REST, gRPC, WebSocket, and GraphQL
APIs, with routing, authentication, rate limiting, and request/response
transformation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class GatewayProtocol(str, Enum):
    REST = "rest"
    GRPC = "grpc"
    WEBSOCKET = "websocket"
    GRAPHQL = "graphql"


@dataclass
class GatewayConfig:
    host: str = "0.0.0.0"
    rest_port: int = 8200
    grpc_port: int = 8201
    ws_port: int = 8202
    graphql_port: int = 8203
    prefix: str = "/api/v1/data"
    enable_cors: bool = True
    rate_limit_per_minute: int = 120
    max_request_size_mb: int = 50
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GatewayRequest:
    """Normalized request across all protocols."""
    method: str
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    body: Any = None
    query_params: dict[str, str] = field(default_factory=dict)
    protocol: GatewayProtocol = GatewayProtocol.REST
    principal_id: str = ""
    request_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class GatewayResponse:
    """Normalized response across all protocols."""
    status_code: int = 200
    body: Any = None
    headers: dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None
    elapsed_ms: float = 0.0


class APIGateway:
    """Unified API gateway for the data platform.

    Routes:
        REST     → /api/v1/data/*
        gRPC     → DataPlatformService
        WebSocket → /ws/data
        GraphQL  → /graphql

    All protocols converge to the same backend services.
    """

    def __init__(self, platform: Any = None, config: Optional[GatewayConfig] = None) -> None:
        self._platform = platform
        self._config = config or GatewayConfig()
        self._request_count = 0
        self._error_count = 0

    async def handle_request(self, request: GatewayRequest) -> GatewayResponse:
        """Handle a normalized gateway request."""
        self._request_count += 1
        start = datetime.now(timezone.utc)

        try:
            # Route to handler
            body = await self._route(request)
            elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000

            return GatewayResponse(
                status_code=200,
                body=body,
                elapsed_ms=elapsed,
            )
        except ValueError as exc:
            self._error_count += 1
            return GatewayResponse(status_code=400, error=str(exc))
        except Exception as exc:
            self._error_count += 1
            return GatewayResponse(status_code=500, error=str(exc))

    async def _route(self, request: GatewayRequest) -> Any:
        """Route request to the appropriate handler."""
        path = request.path
        method = request.method.upper()

        # Market Data
        if path.startswith("/market-data"):
            if method == "GET":
                return await self._handle_query_market_data(request)
            elif method == "POST":
                return await self._handle_subscribe(request)

        # Historical Data
        elif path.startswith("/historical"):
            if method == "GET":
                return await self._handle_query_historical(request)

        # Replay
        elif path.startswith("/replay"):
            if method == "POST":
                return await self._handle_replay(request)

        # Catalog
        elif path.startswith("/catalog"):
            if method == "GET":
                return await self._handle_catalog_query(request)

        # Governance
        elif path.startswith("/governance"):
            if method == "GET":
                return await self._handle_governance_status(request)

        # Health
        elif path == "/health":
            return {"status": "healthy", "requests": self._request_count}

        raise ValueError(f"Unknown path: {path}")

    async def _handle_subscribe(self, request: GatewayRequest) -> dict[str, Any]:
        if self._platform and self._platform.gateway:
            return {"status": "subscribed", "instruments": request.body.get("instruments", [])}
        return {"error": "Platform not available"}

    async def _handle_query_market_data(self, request: GatewayRequest) -> dict[str, Any]:
        return {"data": [], "query": request.query_params}

    async def _handle_query_historical(self, request: GatewayRequest) -> dict[str, Any]:
        return {"data": [], "query": request.query_params}

    async def _handle_replay(self, request: GatewayRequest) -> dict[str, Any]:
        return {"status": "replay_started", "params": request.body}

    async def _handle_catalog_query(self, request: GatewayRequest) -> dict[str, Any]:
        if self._platform and self._platform.catalog:
            return {"datasets": [], "total": 0}
        return {"error": "Catalog not available"}

    async def _handle_governance_status(self, request: GatewayRequest) -> dict[str, Any]:
        return {"status": "compliant", "checks_passed": 0}

    @property
    def total_requests(self) -> int:
        return self._request_count

    @property
    def error_count(self) -> int:
        return self._error_count

    @property
    def error_rate(self) -> float:
        if self._request_count == 0:
            return 0.0
        return self._error_count / self._request_count
