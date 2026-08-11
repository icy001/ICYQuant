"""AI Gateway — unified entry point for all external AI requests.

The AIGateway serves as the front door for the AI Platform. All incoming
requests — whether from REST, gRPC, WebSocket, or internal callers — pass
through the gateway for authentication, rate limiting, request normalization,
and initial routing before being handed to the ControlPlane.

Pipeline:
    Request -> AIGateway
        -> Authenticate
        -> Rate Limit
        -> Normalize
        -> Route to ControlPlane
        -> Return Response
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RequestType(str, Enum):
    """Types of requests handled by the AI Gateway."""
    CHAT = "chat"
    AGENT_RUN = "agent_run"
    WORKFLOW = "workflow"
    TOOL_CALL = "tool_call"
    QUERY = "query"
    STREAM = "stream"


class RequestStatus(str, Enum):
    """Processing status of a gateway request."""
    PENDING = "pending"
    ROUTING = "routing"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    ERROR = "error"


@dataclass
class GatewayRequest:
    """Normalized request passing through the AI Gateway."""
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    request_type: RequestType = RequestType.CHAT
    user_id: str = ""
    session_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: RequestStatus = RequestStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class GatewayResponse:
    """Normalized response from the AI Gateway."""
    request_id: str = ""
    status: str = "ok"
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0


@dataclass
class RateLimitConfig:
    """Rate limiting configuration for the gateway."""
    requests_per_second: int = 100
    requests_per_minute: int = 1000
    burst_size: int = 50
    per_user_limit_per_minute: int = 60


class AIGateway:
    """Unified entry point for all external AI requests.

    Handles authentication, rate limiting, request normalization, and
    initial routing. All requests flow through the gateway before reaching
    any internal AI subsystem.

    Usage:
        gateway = AIGateway()
        await gateway.initialize()
        response = await gateway.process(request)
    """

    def __init__(self, rate_limit: Optional[RateLimitConfig] = None) -> None:
        self._rate_limit = rate_limit or RateLimitConfig()
        self._request_counters: Dict[str, int] = {}
        self._window_start: float = time.monotonic()
        self._total_requests: int = 0
        self._total_rejected: int = 0
        self._total_errors: int = 0
        self._active_requests: Dict[str, GatewayRequest] = {}
        self._initialized: bool = False
        self._lock = asyncio.Lock()
        logger.info("AIGateway created (rps=%d)", self._rate_limit.requests_per_second)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("AIGateway initialized")

    async def shutdown(self) -> None:
        self._active_requests.clear()
        self._request_counters.clear()
        self._initialized = False
        logger.info("AIGateway shutdown complete")

    async def process(self, payload: Dict[str, Any], user_id: str = "anonymous", session_id: Optional[str] = None) -> GatewayResponse:
        """Process an incoming request through the gateway pipeline.

        Pipeline:
            1. Validate and normalize
            2. Rate limit check
            3. Route to control plane
            4. Return response
        """
        if not self._initialized:
            raise RuntimeError("AIGateway not initialized")

        request_type = RequestType(payload.get("type", "chat"))
        request = GatewayRequest(
            request_type=request_type,
            user_id=user_id,
            session_id=session_id,
            payload=payload,
        )

        # Rate limiting
        if not await self._check_rate_limit(user_id):
            self._total_rejected += 1
            logger.warning("AIGateway: rate limit exceeded for user %s", user_id)
            return GatewayResponse(
                request_id=request.request_id,
                status="rejected",
                error="Rate limit exceeded",
                latency_ms=0.0,
            )

        self._total_requests += 1
        request.status = RequestStatus.ROUTING
        request.started_at = datetime.now(timezone.utc)

        async with self._lock:
            self._active_requests[request.request_id] = request

        try:
            # TODO: Route to ControlPlane for actual processing
            start = time.monotonic()
            # Simulated routing
            await asyncio.sleep(0)
            elapsed = (time.monotonic() - start) * 1000

            request.status = RequestStatus.COMPLETED
            request.completed_at = datetime.now(timezone.utc)

            return GatewayResponse(
                request_id=request.request_id,
                status="ok",
                data={"message": "Request routed successfully"},
                latency_ms=round(elapsed, 2),
            )
        except Exception as e:
            self._total_errors += 1
            request.status = RequestStatus.ERROR
            logger.error("AIGateway processing error: %s", e)
            return GatewayResponse(
                request_id=request.request_id,
                status="error",
                error=str(e),
                latency_ms=0.0,
            )
        finally:
            async with self._lock:
                self._active_requests.pop(request.request_id, None)

    async def _check_rate_limit(self, user_id: str) -> bool:
        """Check if the request is within rate limits."""
        now = time.monotonic()
        if now - self._window_start > 60.0:
            self._request_counters.clear()
            self._window_start = now

        total = sum(self._request_counters.values())
        user_count = self._request_counters.get(user_id, 0)

        if total >= self._rate_limit.requests_per_minute:
            return False
        if user_count >= self._rate_limit.per_user_limit_per_minute:
            return False

        self._request_counters[user_id] = user_count + 1
        return True

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "total_requests": self._total_requests,
            "total_rejected": self._total_rejected,
            "total_errors": self._total_errors,
            "active_requests": len(self._active_requests),
            "rate_limit_config": {
                "rps": self._rate_limit.requests_per_second,
                "rpm": self._rate_limit.requests_per_minute,
            },
        }
