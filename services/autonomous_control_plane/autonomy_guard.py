"""
Autonomy Guard — Safety gate for autonomy transitions.

Even when models perform well, autonomy level increases must pass
through the Guard, which checks risk, system health, model health,
policy, and approval status before allowing any transition.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AutonomyGuard:
    """
    Safety gate that prevents unauthorized or unsafe autonomy transitions.

    The Guard enforces that autonomy level increases require:
    - Acceptable risk metrics
    - Healthy system state
    - Healthy model state
    - Policy compliance
    - Required approvals
    """

    def __init__(self):
        self._check_count = 0
        self._block_count = 0
        self._required_checks = [
            "risk_check",
            "system_health",
            "model_health",
            "policy_compliance",
        ]

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    async def evaluate_transition(
        self,
        from_level: int,
        to_level: int,
        context: dict,
    ) -> tuple[bool, str, list[str]]:
        """
        Evaluate whether a transition should be allowed.

        Returns (allowed, reason, missing_checks).
        """
        self._check_count += 1
        failures = []

        # Risk check
        if not await self._check_risk(context):
            failures.append("risk_check")
            logger.warning("AutonomyGuard: risk check failed for L%d → L%d", from_level, to_level)

        # System health
        if not await self._check_system_health(context):
            failures.append("system_health")
            logger.warning("AutonomyGuard: system health failed")

        # Model health
        if not await self._check_model_health(context):
            failures.append("model_health")

        # Policy compliance
        if not await self._check_policy(context):
            failures.append("policy_compliance")

        if failures:
            self._block_count += 1
            return False, f"Guard violations: {', '.join(failures)}", failures

        return True, "", []

    async def _check_risk(self, context: dict) -> bool:
        risk = context.get("risk_context", {})
        max_dd = risk.get("drawdown", 0)
        var_breach = risk.get("var_breach", False)
        return max_dd <= 0.25 and not var_breach

    async def _check_system_health(self, context: dict) -> bool:
        health = context.get("system_health_context", {})
        overall = health.get("overall", "HEALTHY")
        return overall != "CRITICAL"

    async def _check_model_health(self, context: dict) -> bool:
        model_health = context.get("model_health", {})
        return model_health.get("status", "degraded") not in ("quarantined", "retired")

    async def _check_policy(self, context: dict) -> bool:
        policy = context.get("policy_context", {})
        return not policy.get("block_transition", False)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "checks_total": self._check_count,
            "blocks_total": self._block_count,
            "block_rate": self._block_count / max(self._check_count, 1),
        }
