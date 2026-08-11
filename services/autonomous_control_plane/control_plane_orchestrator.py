"""
Control Plane Orchestrator — Cross-domain decision orchestration.

The Orchestrator coordinates complex, multi-step decisions that span
multiple autonomous domains and require coordination across engines.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class OrchestrationStep(Enum):
    """Steps in a cross-domain orchestration workflow."""
    VALIDATE_POLICY = "validate_policy"
    CHECK_AUTONOMY = "check_autonomy"
    CHECK_PERMISSIONS = "check_permissions"
    CHECK_BUDGET = "check_budget"
    CHECK_LIFECYCLE = "check_lifecycle"
    CHECK_HEALTH = "check_health"
    CHECK_APPROVAL = "check_approval"
    EXECUTE_DECISION = "execute_decision"
    AUDIT_DECISION = "audit_decision"


@dataclass
class OrchestrationResult:
    """Result of a complete orchestration pipeline."""
    orchestration_id: str
    success: bool
    final_decision: str
    steps_completed: list[str] = field(default_factory=list)
    steps_failed: list[dict] = field(default_factory=list)
    duration_ms: float = 0.0
    trace_id: str = ""

    def to_dict(self) -> dict:
        return {
            "orchestration_id": self.orchestration_id,
            "success": self.success,
            "final_decision": self.final_decision,
            "steps_completed": self.steps_completed,
            "steps_failed": self.steps_failed,
            "duration_ms": self.duration_ms,
            "trace_id": self.trace_id,
        }


class ControlPlaneOrchestrator:
    """
    Cross-domain decision orchestrator.

    Coordinates complex autonomous decisions that span Research, Alpha,
    Strategy, Portfolio, Risk, and Execution domains, ensuring each
    step passes governance checks before proceeding.
    """

    def __init__(self, control_plane=None):
        self._control_plane = control_plane
        self._pipeline_steps = self._default_pipeline()
        self._orchestration_count = 0

    def bind(self, control_plane) -> None:
        """Bind to a ControlPlane instance."""
        self._control_plane = control_plane

    # ------------------------------------------------------------------
    # Pipeline Configuration
    # ------------------------------------------------------------------

    def _default_pipeline(self) -> list:
        """Default orchestration pipeline — all checks in sequence."""
        return [
            OrchestrationStep.VALIDATE_POLICY,
            OrchestrationStep.CHECK_HEALTH,
            OrchestrationStep.CHECK_AUTONOMY,
            OrchestrationStep.CHECK_PERMISSIONS,
            OrchestrationStep.CHECK_BUDGET,
            OrchestrationStep.CHECK_LIFECYCLE,
            OrchestrationStep.CHECK_APPROVAL,
            OrchestrationStep.EXECUTE_DECISION,
            OrchestrationStep.AUDIT_DECISION,
        ]

    def configure_pipeline(self, steps: list[OrchestrationStep]) -> None:
        """Customize the orchestration pipeline."""
        self._pipeline_steps = steps

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    async def orchestrate(self, context: dict) -> OrchestrationResult:
        """
        Run a complete orchestration pipeline for a cross-domain decision.

        Each step in the pipeline is evaluated in order. If any step
        fails, the pipeline short-circuits and returns the failure result.
        """
        from .control_plane import ControlPlaneContext

        orch_id = str(uuid.uuid4())
        trace_id = context.get("trace_id", orch_id)
        cp_context = ControlPlaneContext(trace_id=trace_id, **context)

        result = OrchestrationResult(
            orchestration_id=orch_id,
            success=False,
            final_decision="pending",
            trace_id=trace_id,
        )

        start = time.time()
        self._orchestration_count += 1

        step_handlers = {
            OrchestrationStep.VALIDATE_POLICY: self._validate_policy,
            OrchestrationStep.CHECK_AUTONOMY: self._check_autonomy,
            OrchestrationStep.CHECK_PERMISSIONS: self._check_permissions,
            OrchestrationStep.CHECK_BUDGET: self._check_budget,
            OrchestrationStep.CHECK_LIFECYCLE: self._check_lifecycle,
            OrchestrationStep.CHECK_HEALTH: self._check_health,
            OrchestrationStep.CHECK_APPROVAL: self._check_approval,
            OrchestrationStep.EXECUTE_DECISION: self._execute_decision,
            OrchestrationStep.AUDIT_DECISION: self._audit_decision,
        }

        try:
            for step in self._pipeline_steps:
                handler = step_handlers.get(step)
                if handler:
                    allowed, reason = await handler(cp_context)
                    if not allowed:
                        result.steps_completed.append(step.value)
                        result.steps_failed.append({
                            "step": step.value,
                            "reason": reason,
                        })
                        result.final_decision = "denied"
                        result.duration_ms = (time.time() - start) * 1000
                        return result
                    result.steps_completed.append(step.value)

            # All steps passed
            result.success = True
            result.final_decision = "allowed"

        except Exception as e:
            logger.exception("Orchestration error: %s", e)
            result.steps_failed.append({
                "step": "exception",
                "reason": str(e),
            })
            result.final_decision = "error"

        result.duration_ms = (time.time() - start) * 1000
        return result

    # ------------------------------------------------------------------
    # Step Handlers
    # ------------------------------------------------------------------

    async def _validate_policy(self, ctx) -> tuple[bool, str]:
        cp = self._control_plane
        if cp and cp.policy_engine:
            policy_result = await cp.policy_engine.evaluate(ctx)
            return policy_result.decision.value == "allow", "policy_violation"
        return True, ""

    async def _check_autonomy(self, ctx) -> tuple[bool, str]:
        cp = self._control_plane
        if cp and cp.autonomy_engine:
            result = await cp.autonomy_engine.evaluate(ctx)
            if not result.allowed:
                return False, f"autonomy_denied: {result.decision.value}"
        return True, ""

    async def _check_permissions(self, ctx) -> tuple[bool, str]:
        cp = self._control_plane
        if cp and cp.permission_engine:
            ok = await cp.permission_engine.check(ctx)
            if not ok.allowed:
                return False, "permission_denied"
        return True, ""

    async def _check_budget(self, ctx) -> tuple[bool, str]:
        cp = self._control_plane
        if cp and cp.budget_manager:
            result = await cp.budget_manager.check(ctx)
            if not result.allowed:
                return False, "budget_exceeded"
        return True, ""

    async def _check_lifecycle(self, ctx) -> tuple[bool, str]:
        cp = self._control_plane
        if cp and cp.lifecycle_engine:
            result = await cp.lifecycle_engine.evaluate(ctx)
            if not result.allowed:
                return False, f"lifecycle: {result.decision.value}"
        return True, ""

    async def _check_health(self, ctx) -> tuple[bool, str]:
        cp = self._control_plane
        if cp and cp.health_monitor:
            health = await cp.health_monitor.check()
            if health.get("overall") == "CRITICAL":
                return False, "system_health_critical"
        return True, ""

    async def _check_approval(self, ctx) -> tuple[bool, str]:
        cp = self._control_plane
        if cp and cp.approval_engine:
            result = await cp.approval_engine.evaluate(ctx)
            if not result.allowed:
                return False, f"approval: {result.decision.value}"
        return True, ""

    async def _execute_decision(self, ctx) -> tuple[bool, str]:
        cp = self._control_plane
        if cp and cp.decision_engine:
            final = await cp.decision_engine.decide(ctx)
            return True, f"decision: {final.value}"
        return True, "decision: allow"

    async def _audit_decision(self, ctx) -> tuple[bool, str]:
        cp = self._control_plane
        if cp and cp.audit_engine:
            await cp.audit_engine.record(ctx)
        return True, "audited"

    # ------------------------------------------------------------------
    # Complex Workflows
    # ------------------------------------------------------------------

    async def strategy_promotion_workflow(
        self, strategy_id: str, from_level: str, to_level: str
    ) -> OrchestrationResult:
        """Orchestrate a strategy promotion through promotion gates."""
        context = {
            "entity_id": strategy_id,
            "entity_type": "strategy",
            "action": f"promote_{from_level}_to_{to_level}",
            "requested_scope": "promotion",
        }
        return await self.orchestrate(context)

    async def autonomous_capital_request(
        self, strategy_id: str, requested_capital: float
    ) -> OrchestrationResult:
        """Orchestrate an autonomous capital allocation request."""
        context = {
            "entity_id": strategy_id,
            "entity_type": "capital_request",
            "action": "allocate_capital",
            "requested_capital": requested_capital,
            "requested_scope": "capital",
        }
        return await self.orchestrate(context)

    async def emergency_procedure(self, reason: str) -> OrchestrationResult:
        """Orchestrate an emergency procedure."""
        context = {
            "entity_id": "system",
            "entity_type": "emergency",
            "action": "emergency_procedure",
            "reason": reason,
            "requested_scope": "system_wide",
        }
        return await self.orchestrate(context)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "orchestrations_total": self._orchestration_count,
            "pipeline_steps": [s.value for s in self._pipeline_steps],
        }
