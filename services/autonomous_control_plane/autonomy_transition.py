"""
Autonomy Transition — Manages progressive autonomy level transitions.

Controls the process of moving between autonomy levels with
proper validation, approval requirements, and audit trail.
"""

from __future__ import annotations

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AutonomyTransition:
    """
    Manages transitions between autonomy levels.

    Enforces:
    - Progressive level increases (no skipping)
    - Mandatory cooldown periods
    - Required approvals for higher levels
    - Full audit trail of all transitions
    """

    def __init__(self, autonomy_engine=None, autonomy_policy=None):
        from .autonomy_engine import AutonomyEngine
        from .autonomy_policy import AutonomyPolicy
        self._engine = autonomy_engine or AutonomyEngine()
        self._policy = autonomy_policy or AutonomyPolicy()
        self._transitions: list[dict] = []
        self._cooldown_until: float = 0.0
        self._cooldown_seconds = 86400  # 24 hours between promotions

    # ------------------------------------------------------------------
    # Transition Management
    # ------------------------------------------------------------------

    async def request_promotion(
        self, target_level: int, context: dict, operator: str = ""
    ) -> dict:
        """
        Request a promotion to a higher autonomy level.
        Returns result with allowed, reason, and required approvals.
        """
        current = await self._engine.current_level()

        # Validate target
        can_transition, reason = self._engine.can_transition_to(target_level)
        if not can_transition:
            return {"allowed": False, "reason": reason}

        if target_level <= current:
            return {"allowed": False, "reason": "Target level must be higher"}

        # Check cooldown
        if time.time() < self._cooldown_until:
            remaining = int(self._cooldown_until - time.time())
            return {"allowed": False, "reason": f"Cooldown: {remaining}s remaining"}

        # Evaluate promotion rules
        ok, failures = self._policy.evaluate_promotion(context)
        if not ok:
            return {
                "allowed": False,
                "reason": "Promotion rules not satisfied",
                "failures": failures,
            }

        # Levels 5+ require manual approval
        requires_approval = target_level >= 5

        return {
            "allowed": True,
            "target_level": target_level,
            "current_level": current,
            "requires_approval": requires_approval,
            "approval_required_for": "L5+" if requires_approval else None,
        }

    async def execute_promotion(self, target_level: int, operator: str = "") -> bool:
        """Execute an approved promotion."""
        self._cooldown_until = time.time() + self._cooldown_seconds
        result = self._engine.set_level(target_level, "promotion", operator)
        if result:
            self._transitions.append({
                "direction": "promote",
                "to": target_level,
                "operator": operator,
                "timestamp": time.time(),
            })
        return result

    async def request_demotion(
        self, reason: str, context: dict, operator: str = ""
    ) -> dict:
        """Request a demotion — either triggered automatically or manually."""
        current = await self._engine.current_level()
        target = max(current - 1, 0)

        # Check demotion rules
        triggered, triggers = self._policy.evaluate_demotion(context)

        return {
            "allowed": True,  # Demotion is always allowed
            "target_level": target,
            "current_level": current,
            "triggered": triggered,
            "triggers": triggers,
            "reason": reason,
        }

    async def execute_demotion(self, reason: str, operator: str = "") -> bool:
        """Execute a demotion."""
        current = await self._engine.current_level()
        target = max(current - 1, 0)
        result = self._engine.set_level(target, reason, operator)
        if result:
            self._transitions.append({
                "direction": "demote",
                "to": target,
                "operator": operator,
                "reason": reason,
                "timestamp": time.time(),
            })
        return result

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def history(self) -> list[dict]:
        return list(self._transitions)

    def stats(self) -> dict:
        return {
            "transitions_total": len(self._transitions),
            "cooldown_remaining": max(0, int(self._cooldown_until - time.time())),
        }
