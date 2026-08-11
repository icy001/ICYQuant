"""
Risk Controller — Central orchestration for risk evaluation workflows.

Coordinates policy evaluation, approval decisions, and audit
recording across all risk checks.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ControllerDecision(str, Enum):
    """Controller-level decisions."""
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"
    PENDING = "pending"


@dataclass
class EvaluationContext:
    """Context for a single risk evaluation."""
    evaluation_id: str
    component_id: str
    policy_ids: list[str] = field(default_factory=list)
    results: dict[str, bool] = field(default_factory=dict)
    violations: list[dict[str, Any]] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


class RiskController:
    """
    Central controller for risk evaluation orchestration.

    Orchestrates the Policy → Evaluation → Approval → Audit workflow,
    coordinating between the runtime, registry, and executor.

    Usage::

        controller = RiskController(runtime=rt)
        await controller.initialize()
        decision = await controller.evaluate(context)
    """

    def __init__(self, runtime: Any = None) -> None:
        self._runtime = runtime
        self._evaluations: dict[str, EvaluationContext] = {}
        self._counter: int = 0
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the risk controller."""
        logger.info("RiskController initialized.")

    async def stop(self) -> None:
        """Stop the risk controller."""
        logger.info("RiskController stopped.")

    # ---- Evaluation ----

    async def start_evaluation(
        self,
        component_id: str,
        policy_ids: Optional[list[str]] = None,
    ) -> EvaluationContext:
        """Start a new risk evaluation."""
        self._counter += 1
        ctx = EvaluationContext(
            evaluation_id=f"eval_{self._counter:06d}",
            component_id=component_id,
            policy_ids=policy_ids or [],
        )
        self._evaluations[ctx.evaluation_id] = ctx
        logger.debug(f"Evaluation started: {ctx.evaluation_id}")
        return ctx

    async def record_result(
        self,
        evaluation_id: str,
        policy_id: str,
        passed: bool,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record a policy evaluation result."""
        ctx = self._evaluations.get(evaluation_id)
        if not ctx:
            return
        ctx.results[policy_id] = passed
        if not passed and details:
            ctx.violations.append({"policy_id": policy_id, **details})

    async def decide(self, evaluation_id: str) -> ControllerDecision:
        """Make a final decision based on all policy results."""
        ctx = self._evaluations.get(evaluation_id)
        if not ctx:
            return ControllerDecision.REJECT

        ctx.completed_at = datetime.now(timezone.utc)

        if not ctx.results:
            return ControllerDecision.APPROVE

        all_passed = all(ctx.results.values())
        if all_passed:
            return ControllerDecision.APPROVE
        elif any(ctx.results.values()):
            return ControllerDecision.ESCALATE
        else:
            return ControllerDecision.REJECT

    async def get_evaluation(self, evaluation_id: str) -> Optional[EvaluationContext]:
        """Get an evaluation context."""
        return self._evaluations.get(evaluation_id)

    async def list_evaluations(self, limit: int = 100) -> list[EvaluationContext]:
        """List recent evaluations."""
        return list(self._evaluations.values())[-limit:]

    async def health_check(self) -> dict[str, Any]:
        """Check controller health."""
        return {
            "status": "healthy",
            "active_evaluations": len(self._evaluations),
        }
