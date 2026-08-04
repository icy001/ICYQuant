"""
Canary promotion logic.

Handles the decision-making for promoting
a canary deployment to the next stage based
on health check results and policy settings.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .health import HealthStatus
from .policy import CanaryPolicy
from .stage import CanaryDeployment


class PromotionEngine:
    """
    Evaluates promotion readiness for canary deployments.

    Determines whether a canary deployment is
    ready to advance to the next stage based
    on health metrics, duration, and policy.

    Usage:
        engine = PromotionEngine(policy=CanaryPolicy())
        decision = engine.evaluate(deployment, health_result)
        if decision.can_promote:
            await dm.promote()
    """

    def __init__(self, policy: Optional[CanaryPolicy] = None) -> None:
        """
        Initialize the promotion engine.

        Args:
            policy: Canary policy for promotion decisions.
        """
        self._policy = policy or CanaryPolicy()

    def evaluate(
        self,
        deployment: CanaryDeployment,
        health_result: Any,
        request_count: int = 0,
        elapsed_seconds: float = 0.0,
    ) -> PromotionDecision:
        """
        Evaluate whether promotion is possible.

        Args:
            deployment: Current deployment state.
            health_result: Latest health check result.
            request_count: Total requests in current stage.
            elapsed_seconds: Time elapsed in current stage.

        Returns:
            PromotionDecision with details.
        """
        decision = PromotionDecision(can_promote=False)

        # Cannot promote if not running
        if deployment.status != "running":
            decision.reason = f"Deployment not running: {deployment.status}"
            return decision

        # Cannot promote if at last stage
        if deployment.current_stage_index >= len(deployment.stages) - 1:
            decision.reason = "Already at final stage"
            return decision

        # Check if auto_promote is enabled for this stage
        stage = deployment.current_stage
        if not stage.auto_promote and not self._policy.auto_promote:
            decision.reason = "Auto-promote disabled for this stage"
            return decision

        # Check minimum sample size
        if request_count < self._policy.min_sample_size:
            decision.reason = (
                f"Insufficient samples: {request_count} < {self._policy.min_sample_size}"
            )
            return decision

        # Check health
        if health_result.status == HealthStatus.CRITICAL:
            decision.reason = f"Health critical: score={health_result.score:.1f}"
            decision.should_rollback = True
            return decision

        if health_result.status != HealthStatus.HEALTHY:
            decision.reason = f"Health not OK: {health_result.status}"
            return decision

        # Check duration
        min_duration = stage.duration.total_seconds()
        if elapsed_seconds < min_duration:
            decision.reason = (
                f"Duration not met: {elapsed_seconds:.0f}s < {min_duration:.0f}s"
            )
            return decision

        # All checks passed
        decision.can_promote = True
        decision.reason = "All checks passed"
        decision.next_percentage = deployment.stages[
            deployment.current_stage_index + 1
        ].percentage
        return decision


class PromotionDecision:
    """
    Result of a promotion evaluation.

    Attributes:
        can_promote: Whether promotion is allowed.
        reason: Reason for the decision.
        should_rollback: Whether a rollback is recommended.
        next_percentage: Percentage for the next stage.
    """

    def __init__(
        self,
        can_promote: bool = False,
        reason: str = "",
        should_rollback: bool = False,
        next_percentage: float = 0.0,
    ) -> None:
        self.can_promote = can_promote
        self.reason = reason
        self.should_rollback = should_rollback
        self.next_percentage = next_percentage

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "can_promote": self.can_promote,
            "reason": self.reason,
            "should_rollback": self.should_rollback,
            "next_percentage": self.next_percentage,
        }
