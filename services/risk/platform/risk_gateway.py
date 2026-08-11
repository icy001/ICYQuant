"""
Risk Gateway — Unified entry point for all trading risk evaluations.

All requests from Strategy Platform, OMS, EMS, and external systems
flow through this gateway for centralized risk control.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class GatewayDecision(str, Enum):
    """Gateway-level risk decisions."""
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING_REVIEW = "pending_review"
    BLOCKED = "blocked"
    ERROR = "error"


class RequestSource(str, Enum):
    """Source of a risk evaluation request."""
    STRATEGY_PLATFORM = "strategy_platform"
    OMS = "oms"
    EMS = "ems"
    WORKFLOW = "workflow"
    RESEARCH = "research"
    AI_AGENT = "ai_agent"
    EXTERNAL = "external"
    API = "api"


@dataclass
class GatewayRequest:
    """A risk evaluation request entering the gateway."""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: RequestSource = RequestSource.API
    strategy_id: str = ""
    order_data: dict[str, Any] = field(default_factory=dict)
    portfolio_id: str = ""
    account_id: str = ""
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class GatewayResponse:
    """A risk evaluation response from the gateway."""
    request_id: str = ""
    decision: GatewayDecision = GatewayDecision.PENDING_REVIEW
    reason: str = ""
    latency_ms: float = 0.0
    evaluation_details: dict[str, Any] = field(default_factory=dict)
    audit_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class GatewayStats:
    """Gateway operational statistics."""
    requests_total: int = 0
    requests_approved: int = 0
    requests_rejected: int = 0
    requests_blocked: int = 0
    avg_latency_ms: float = 0.0
    last_request_at: Optional[datetime] = None


class RiskGateway:
    """
    Unified entry point for all trading risk evaluations.

    All incoming trading requests must pass through this gateway
    for centralized risk assessment before reaching OMS/EMS.

    Usage::

        gateway = RiskGateway(platform=platform)
        await gateway.initialize()

        request = GatewayRequest(source=RequestSource.STRATEGY_PLATFORM)
        response = await gateway.evaluate(request)
    """

    def __init__(
        self,
        platform: Any = None,
        max_queue_size: int = 10000,
    ) -> None:
        self._platform = platform
        self._max_queue_size = max_queue_size
        self._stats = GatewayStats()
        self._pre_hooks: list[Callable] = []
        self._post_hooks: list[Callable] = []
        self._latencies: list[float] = []
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the risk gateway."""
        self._initialized = True
        logger.info("RiskGateway initialized.")

    async def stop(self) -> None:
        """Stop the risk gateway."""
        self._initialized = False
        logger.info("RiskGateway stopped.")

    # ---- Core Gateway Operations ----

    async def evaluate(self, request: GatewayRequest) -> GatewayResponse:
        """Evaluate a risk request through the gateway pipeline."""
        start = time.monotonic()

        # Run pre-hooks
        for hook in self._pre_hooks:
            try:
                await hook(request)
            except Exception as e:
                logger.error(f"Pre-hook error: {e}")

        try:
            # Rate limiting
            if self._stats.requests_active() > 1000:
                return GatewayResponse(
                    request_id=request.request_id,
                    decision=GatewayDecision.BLOCKED,
                    reason="rate_limit_exceeded",
                )

            # Delegate to platform evaluation
            decision, reason, details = await self._evaluate_request(request)

            latency_ms = (time.monotonic() - start) * 1000

            response = GatewayResponse(
                request_id=request.request_id,
                decision=decision,
                reason=reason,
                latency_ms=latency_ms,
                evaluation_details=details,
                audit_id=str(uuid.uuid4()),
            )

            # Update stats
            async with self._lock:
                self._stats.requests_total += 1
                if decision == GatewayDecision.APPROVED:
                    self._stats.requests_approved += 1
                elif decision == GatewayDecision.REJECTED:
                    self._stats.requests_rejected += 1
                elif decision == GatewayDecision.BLOCKED:
                    self._stats.requests_blocked += 1
                self._stats.last_request_at = datetime.now(timezone.utc)
                self._latencies.append(latency_ms)
                if len(self._latencies) > 10000:
                    self._latencies = self._latencies[-10000:]
                self._stats.avg_latency_ms = (
                    sum(self._latencies) / len(self._latencies) if self._latencies else 0
                )

            # Run post-hooks
            for hook in self._post_hooks:
                try:
                    await hook(request, response)
                except Exception as e:
                    logger.error(f"Post-hook error: {e}")

            # Publish audit event
            await self._publish_audit_event(request, response)

            return response

        except Exception as e:
            logger.error(f"Gateway evaluation error: {e}")
            return GatewayResponse(
                request_id=request.request_id,
                decision=GatewayDecision.ERROR,
                reason=str(e),
                latency_ms=(time.monotonic() - start) * 1000,
            )

    async def approve(self, request_id: str) -> GatewayResponse:
        """Approve a pending request."""
        return GatewayResponse(
            request_id=request_id,
            decision=GatewayDecision.APPROVED,
            reason="manual_approval",
        )

    async def reject(self, request_id: str) -> GatewayResponse:
        """Reject a pending request."""
        return GatewayResponse(
            request_id=request_id,
            decision=GatewayDecision.REJECTED,
            reason="manual_rejection",
        )

    async def publish(self, event_type: str, data: dict[str, Any]) -> bool:
        """Publish a risk event through the gateway."""
        logger.debug(f"Gateway published event: {event_type}")
        return True

    # ---- Hook Registration ----

    def add_pre_hook(self, hook: Callable) -> None:
        """Register a pre-evaluation hook."""
        self._pre_hooks.append(hook)

    def add_post_hook(self, hook: Callable) -> None:
        """Register a post-evaluation hook."""
        self._post_hooks.append(hook)

    # ---- Statistics ----

    async def get_stats(self) -> GatewayStats:
        """Get current gateway statistics."""
        return self._stats

    async def get_queue_depth(self) -> int:
        """Get current request queue depth."""
        return 0  # In-memory, no queue backlog

    # ---- Internal ----

    async def _evaluate_request(
        self,
        request: GatewayRequest,
    ) -> tuple[GatewayDecision, str, dict[str, Any]]:
        """Evaluate request through the platform pipeline."""
        # Pre-trade checks
        if not request.strategy_id:
            return GatewayDecision.BLOCKED, "missing_strategy_id", {}

        # Delegate to platform
        if self._platform:
            result = await self._platform.evaluate_order(request.order_data)
            decision_str = result.get("decision", "approved")
            decision_map = {
                "approved": GatewayDecision.APPROVED,
                "rejected": GatewayDecision.REJECTED,
                "pending_review": GatewayDecision.PENDING_REVIEW,
            }
            decision = decision_map.get(decision_str, GatewayDecision.PENDING_REVIEW)
            return decision, result.get("reason", ""), result
        else:
            return GatewayDecision.APPROVED, "default_approval", {"mode": "passthrough"}

    async def _publish_audit_event(
        self,
        request: GatewayRequest,
        response: GatewayResponse,
    ) -> None:
        """Publish audit event for gateway activity."""
        try:
            if self._platform:
                audit_adapter = await self._platform.get_adapter("event_bus")
                if audit_adapter:
                    await audit_adapter.publish("risk.gateway.evaluation", {
                        "request_id": request.request_id,
                        "source": request.source.value,
                        "decision": response.decision.value,
                        "latency_ms": response.latency_ms,
                    })
        except Exception as e:
            logger.debug(f"Audit publish skipped: {e}")

    async def health_check(self) -> dict[str, Any]:
        """Check gateway health."""
        return {
            "status": "healthy" if self._initialized else "stopped",
            "requests_total": self._stats.requests_total,
            "avg_latency_ms": self._stats.avg_latency_ms,
            "approval_rate": (
                self._stats.requests_approved / max(1, self._stats.requests_total)
                if self._stats.requests_total > 0 else 0
            ),
        }
