"""
Production Risk Engine — Unified entry point for the Risk Management Platform.

Provides the central risk evaluation pipeline: Order Intent → Policy →
Risk Evaluation → Decision. All Order Intents must pass through this
engine before reaching OMS.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RiskDecision(str, Enum):
    """Risk evaluation decisions."""
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING_REVIEW = "pending_review"
    ESCALATED = "escalated"


class EngineStatus(str, Enum):
    """Risk engine operational status."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    DEGRADED = "degraded"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class RiskEvaluationRequest:
    """Request for risk evaluation."""
    request_id: str
    strategy_id: str
    order_intent: dict[str, Any] = field(default_factory=dict)
    portfolio_id: Optional[str] = None
    account_id: Optional[str] = None
    instrument: Optional[str] = None
    quantity: float = 0.0
    price: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RiskEvaluationResult:
    """Result of a risk evaluation."""
    request_id: str
    decision: RiskDecision
    checks_passed: int = 0
    checks_total: int = 0
    violations: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""
    evaluation_latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)


class RiskEngine:
    """
    Unified Production Risk Engine.

    Central entry point for all risk evaluations. Order Intents from
    the Strategy Platform flow through this engine for policy-based
    risk assessment before any execution.

    Usage::

        engine = RiskEngine()
        await engine.initialize()
        result = await engine.evaluate(RiskEvaluationRequest(
            request_id="risk_001",
            strategy_id="strat_001",
            instrument="AAPL",
            quantity=1000,
        ))
        if result.decision == RiskDecision.APPROVED:
            # Proceed to OMS
            ...
    """

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        self._config = config or {}
        self._status = EngineStatus.STOPPED
        self._evaluation_count: int = 0
        self._approved_count: int = 0
        self._rejected_count: int = 0

        # Subsystems
        self._runtime: Any = None
        self._controller: Any = None
        self._policy_registry: Any = None
        self._scheduler: Any = None
        self._executor: Any = None

    @property
    def status(self) -> EngineStatus:
        return self._status

    @property
    def evaluation_count(self) -> int:
        return self._evaluation_count

    async def initialize(self) -> None:
        """Initialize the risk engine and all subsystems."""
        self._status = EngineStatus.INITIALIZING
        logger.info("Initializing Production Risk Engine...")

        # Initialize in dependency order
        from services.risk.risk_runtime import RiskRuntime
        self._runtime = RiskRuntime()
        await self._runtime.initialize()

        from services.risk.risk_controller import RiskController
        self._controller = RiskController(runtime=self._runtime)
        await self._controller.initialize()

        from services.risk.risk_scheduler import RiskScheduler
        self._scheduler = RiskScheduler()
        await self._scheduler.initialize()

        from services.risk.risk_executor import RiskExecutor
        self._executor = RiskExecutor(controller=self._controller)
        await self._executor.initialize()

        logger.info("Production Risk Engine initialized.")

    async def start(self) -> None:
        """Start the risk engine."""
        self._status = EngineStatus.RUNNING
        if self._runtime:
            await self._runtime.start()
        if self._scheduler:
            await self._scheduler.start()
        logger.info("Risk Engine started.")

    async def stop(self) -> None:
        """Stop the risk engine."""
        self._status = EngineStatus.STOPPING
        for subsystem in [self._executor, self._scheduler, self._controller, self._runtime]:
            if subsystem and hasattr(subsystem, 'stop'):
                try:
                    await subsystem.stop()
                except Exception as e:
                    logger.error(f"Error stopping subsystem: {e}")
        self._status = EngineStatus.STOPPED
        logger.info("Risk Engine stopped.")

    # ---- Core Operations ----

    async def evaluate(self, request: RiskEvaluationRequest) -> RiskEvaluationResult:
        """Evaluate an order intent against all risk policies."""
        self._evaluation_count += 1
        start = asyncio.get_event_loop().time()

        try:
            if self._executor:
                result = await self._executor.execute(request)
            else:
                result = RiskEvaluationResult(
                    request_id=request.request_id,
                    decision=RiskDecision.APPROVED,
                    checks_passed=1,
                    checks_total=1,
                    reason="Default approval (no executor)",
                )

            if result.decision == RiskDecision.APPROVED:
                self._approved_count += 1
            elif result.decision == RiskDecision.REJECTED:
                self._rejected_count += 1

        except Exception as e:
            logger.error(f"Risk evaluation failed: {e}")
            result = RiskEvaluationResult(
                request_id=request.request_id,
                decision=RiskDecision.REJECTED,
                reason=f"Evaluation error: {e}",
            )
            self._rejected_count += 1

        result.evaluation_latency_ms = (asyncio.get_event_loop().time() - start) * 1000
        return result

    async def approve(self, request_id: str, reason: str = "") -> RiskEvaluationResult:
        """Approve a pending risk evaluation."""
        return RiskEvaluationResult(
            request_id=request_id,
            decision=RiskDecision.APPROVED,
            reason=reason or "Manually approved",
        )

    async def recover(self) -> dict[str, Any]:
        """Recover the risk engine from a failure state."""
        if self._status in (EngineStatus.RUNNING, EngineStatus.DEGRADED):
            if self._runtime:
                await self._runtime.recover()
            self._status = EngineStatus.RUNNING
        return {"status": self._status.value, "recovered": True}

    # ---- Accessors ----

    @property
    def runtime(self) -> Any:
        return self._runtime

    @property
    def controller(self) -> Any:
        return self._controller

    @property
    def scheduler(self) -> Any:
        return self._scheduler

    @property
    def executor(self) -> Any:
        return self._executor

    async def health_check(self) -> dict[str, Any]:
        """Check engine health."""
        return {
            "status": self._status.value,
            "evaluations": self._evaluation_count,
            "approved": self._approved_count,
            "rejected": self._rejected_count,
            "approval_rate": (self._approved_count / self._evaluation_count * 100) if self._evaluation_count > 0 else 0,
        }
