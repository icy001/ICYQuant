"""
Canary rollback management.

Provides automatic and manual rollback
capabilities for canary deployments.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from .health import HealthStatus
from .policy import CanaryPolicy
from .stage import CanaryDeployment

logger = logging.getLogger(__name__)


class RollbackManager:
    """
    Manages canary deployment rollbacks.

    Supports three types of rollback:
        - Manual: Operator-initiated rollback
        - Automatic: Health-triggered rollback
        - Emergency: Immediate rollback to 0%

    Usage:
        rb = RollbackManager(policy=CanaryPolicy())
        rolled = await rb.execute_rollback(
            deployment=deployment,
            reason="error_rate_exceeded",
            rollback_type="automatic",
        )
    """

    def __init__(self, policy: Optional[CanaryPolicy] = None) -> None:
        """
        Initialize the rollback manager.

        Args:
            policy: Canary policy for rollback decisions.
        """
        self._policy = policy or CanaryPolicy()
        self._rollback_history: List[Dict[str, Any]] = []
        self._callbacks: List[Callable] = []
        self._total_rollbacks = 0
        self._automatic_rollbacks = 0
        self._emergency_rollbacks = 0

    async def execute_rollback(
        self,
        deployment: CanaryDeployment,
        reason: str = "",
        rollback_type: str = "manual",
    ) -> bool:
        """
        Execute a rollback on a deployment.

        Args:
            deployment: Deployment to rollback.
            reason: Reason for rollback.
            rollback_type: Type of rollback (manual, automatic, emergency).

        Returns:
            True if rollback succeeded.
        """
        if rollback_type == "emergency":
            return await self._emergency_rollback(deployment, reason)

        if deployment.current_stage_index <= 0:
            logger.warning(
                "Cannot rollback: already at initial stage for %s",
                deployment.feature_key,
            )
            return False

        previous_percentage = deployment.current_percentage
        deployment.current_stage_index -= 1
        deployment.status = "running"

        # Record
        self._total_rollbacks += 1
        if rollback_type == "automatic":
            self._automatic_rollbacks += 1

        entry = {
            "deployment_id": deployment.deployment_id,
            "feature_key": deployment.feature_key,
            "rollback_type": rollback_type,
            "from_percentage": previous_percentage,
            "to_percentage": deployment.current_percentage,
            "reason": reason,
            "timestamp": time.time(),
        }
        self._rollback_history.append(entry)

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(entry)
            except Exception as e:
                logger.warning("Rollback callback error: %s", e)

        logger.info(
            "ROLLBACK: %s %s %.1f%% -> %.1f%% reason=%s",
            rollback_type.upper(),
            deployment.feature_key,
            previous_percentage,
            deployment.current_percentage,
            reason,
        )
        return True

    async def _emergency_rollback(
        self,
        deployment: CanaryDeployment,
        reason: str = "",
    ) -> bool:
        """Execute an emergency rollback to 0%."""
        previous_percentage = deployment.current_percentage
        deployment.current_stage_index = 0
        deployment.status = "rolled_back"
        deployment.completed_at = time.time()

        self._total_rollbacks += 1
        self._emergency_rollbacks += 1

        entry = {
            "deployment_id": deployment.deployment_id,
            "feature_key": deployment.feature_key,
            "rollback_type": "emergency",
            "from_percentage": previous_percentage,
            "to_percentage": 0.0,
            "reason": reason or "emergency_rollback",
            "timestamp": time.time(),
        }
        self._rollback_history.append(entry)

        for callback in self._callbacks:
            try:
                callback(entry)
            except Exception as e:
                logger.warning("Rollback callback error: %s", e)

        logger.critical(
            "EMERGENCY ROLLBACK: %s %.1f%% -> 0%% reason=%s",
            deployment.feature_key,
            previous_percentage,
            reason,
        )
        return True

    def should_auto_rollback(
        self,
        error_rate: float,
    ) -> bool:
        """
        Check if automatic rollback should be triggered.

        Args:
            error_rate: Current error rate percentage.

        Returns:
            True if rollback should trigger.
        """
        if not self._policy.rollback_on_failure:
            return False
        return error_rate >= self._policy.rollback_threshold

    def on_rollback(self, callback: Callable) -> None:
        """Register a rollback callback."""
        self._callbacks.append(callback)

    def get_history(
        self,
        feature_key: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get rollback history."""
        entries = list(reversed(self._rollback_history))
        if feature_key:
            entries = [e for e in entries if e.get("feature_key") == feature_key]
        return entries[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get rollback statistics."""
        return {
            "total_rollbacks": self._total_rollbacks,
            "automatic_rollbacks": self._automatic_rollbacks,
            "emergency_rollbacks": self._emergency_rollbacks,
            "history_size": len(self._rollback_history),
        }
