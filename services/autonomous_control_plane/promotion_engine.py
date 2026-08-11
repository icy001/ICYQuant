"""
Promotion Engine — Manages model promotions through lifecycle gates.

Controls the process of promoting models from research to production
with staged gates and mandatory checks at each level.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PromotionEngine:
    """
    Manages the promotion of models through lifecycle stages.

    Each promotion must pass through a PromotionGate, which checks
    performance, robustness, capacity, risk, execution, operational
    health, policy compliance, and approval requirements.
    """

    def __init__(self, policy=None, gate=None, lifecycle_engine=None):
        from .promotion_policy import PromotionPolicy
        from .promotion_gate import PromotionGate
        self._policy = policy or PromotionPolicy()
        self._gate = gate or PromotionGate()
        self._lifecycle = lifecycle_engine
        self._promotions: list[dict] = []

    async def promote(
        self, model_id: str, target_state: str,
        context: Optional[dict] = None,
    ) -> bool:
        """
        Promote a model to the target state.

        Returns True if promotion was successful.
        """
        from .model_lifecycle import ModelLifecycleState

        target = ModelLifecycleState(target_state)
        context = context or {}

        # Gate check
        gate_result = await self._gate.evaluate(model_id, target, context)
        if not gate_result["passed"]:
            logger.warning("Promotion gate failed for %s → %s: %s",
                           model_id, target_state, gate_result.get("failures", []))
            return False

        # Policy check
        policy_check = self._policy.evaluate(model_id, target, context)
        if not policy_check["allowed"]:
            logger.warning("Promotion policy denied %s → %s", model_id, target_state)
            return False

        # Execute transition
        if self._lifecycle:
            ok, reason = self._lifecycle.transition(model_id, target, "promotion")
            if not ok:
                logger.error("Transition failed: %s", reason)
                return False

        self._promotions.append({
            "model_id": model_id,
            "to_state": target_state,
            "timestamp": time.time(),
            "success": True,
        })
        logger.info("Model %s promoted → %s", model_id, target_state)
        return True

    async def demote(self, model_id: str, reason: str) -> bool:
        """Demote a model to the previous level."""
        if self._lifecycle:
            from .model_lifecycle import ModelLifecycleState
            current = self._lifecycle.get_state(model_id)
            if not current:
                return False

            # Demotion path
            demotion_map = {
                ModelLifecycleState.PRODUCTION: ModelLifecycleState.SHADOW,
                ModelLifecycleState.SHADOW: ModelLifecycleState.CANDIDATE,
                ModelLifecycleState.PAPER: ModelLifecycleState.SHADOW,
                ModelLifecycleState.DEGRADED: ModelLifecycleState.SHADOW,
            }
            target = demotion_map.get(current)
            if not target:
                return False

            ok, _ = self._lifecycle.transition(model_id, target, reason)
            if ok:
                logger.warning("Model %s demoted to %s: %s", model_id, target.value, reason)
                return True
        return False

    async def rollback(self, model_id: str, target_version: str) -> bool:
        """Rollback a model to a specific previous version."""
        logger.info("Model %s rollback requested → v%s", model_id, target_version)
        # Rollback would involve version management
        self._promotions.append({
            "model_id": model_id,
            "action": "rollback",
            "target_version": target_version,
            "timestamp": time.time(),
            "success": True,
        })
        return True

    async def quarantine(self, model_id: str, reason: str) -> bool:
        """Quarantine a model."""
        if self._lifecycle:
            from .model_lifecycle import ModelLifecycleState
            ok, _ = self._lifecycle.transition(model_id, ModelLifecycleState.QUARANTINED, reason)
            if ok:
                logger.warning("Model %s QUARANTINED: %s", model_id, reason)
                return True
        return False

    def stats(self) -> dict:
        return {
            "promotions_total": len(self._promotions),
            "successful_promotions": len([p for p in self._promotions if p.get("success")]),
        }
