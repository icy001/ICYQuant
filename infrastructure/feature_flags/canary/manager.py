"""
Canary release manager.

Unified entry point for canary release operations.
Coordinates deployment, health monitoring,
promotion, and rollback.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

from .audit import CanaryAudit
from .deployment import CanaryDeploymentManager
from .health import HealthMonitor, HealthStatus
from .metrics import CanaryMetrics
from .monitor import CanaryMonitor
from .policy import CanaryPolicy
from .promotion import PromotionEngine
from .rollback import RollbackManager
from .stage import CanaryDeployment, CanaryStage, DEFAULT_CANARY_STAGES
from .validator import CanaryValidator


class CanaryManager:
    """
    Unified canary release manager.

    Orchestrates canary deployments with
    automatic health monitoring, promotion,
    and rollback capabilities.

    Usage:
        manager = CanaryManager()
        deployment = await manager.start_deployment("new-risk")
        # Record requests for health monitoring
        manager.record_request("new-risk", latency_ms=45.0)
        # Promote when healthy
        promoted = await manager.promote("new-risk")
    """

    def __init__(
        self,
        policy: Optional[CanaryPolicy] = None,
    ) -> None:
        """
        Initialize the canary manager.

        Args:
            policy: Default deployment policy.
        """
        self._policy = policy or CanaryPolicy()
        self._deployments: Dict[str, CanaryDeploymentManager] = {}
        self._promotion_engine = PromotionEngine(self._policy)
        self._rollback_manager = RollbackManager(self._policy)
        self._health_monitors: Dict[str, HealthMonitor] = {}
        self._monitor = CanaryMonitor()
        self._metrics = CanaryMetrics()
        self._audit = CanaryAudit()
        self._validator = CanaryValidator()
        self._lock = asyncio.Lock()

    async def start_deployment(
        self,
        feature_key: str,
        stages: Optional[List[CanaryStage]] = None,
        policy: Optional[CanaryPolicy] = None,
    ) -> CanaryDeployment:
        """
        Start a new canary deployment.

        Args:
            feature_key: Feature flag key.
            stages: Custom deployment stages.
            policy: Optional override policy.

        Returns:
            CanaryDeployment instance.
        """
        effective_policy = policy or self._policy
        deployment = CanaryDeployment(
            deployment_id=f"canary-{feature_key}",
            feature_key=feature_key,
            stages=stages or list(DEFAULT_CANARY_STAGES),
        )

        dm = CanaryDeploymentManager(deployment, effective_policy)
        self._deployments[feature_key] = dm
        self._health_monitors[feature_key] = HealthMonitor()

        await dm.start()
        self._metrics.record_stage(feature_key, 0, deployment.current_percentage)

        return deployment

    async def promote(
        self,
        feature_key: str,
        force: bool = False,
    ) -> bool:
        """
        Promote a canary deployment to the next stage.

        Args:
            feature_key: Feature flag key.
            force: Force promotion.

        Returns:
            True if promoted.
        """
        dm = self._deployments.get(feature_key)
        if not dm:
            return False

        previous_percentage = dm.current_percentage
        promoted = await dm.promote(force=force)

        if promoted:
            self._metrics.record_promotion(feature_key)
            self._metrics.record_stage(
                feature_key,
                dm.deployment.current_stage_index,
                dm.current_percentage,
            )
            await self._audit.record_promotion(
                feature_key,
                dm.deployment.current_stage_index - 1,
                previous_percentage,
                dm.current_percentage,
            )

        return promoted

    async def rollback(
        self,
        feature_key: str,
        reason: str = "",
        rollback_type: str = "manual",
    ) -> bool:
        """
        Rollback a canary deployment.

        Args:
            feature_key: Feature flag key.
            reason: Reason for rollback.
            rollback_type: Type of rollback.

        Returns:
            True if rolled back.
        """
        dm = self._deployments.get(feature_key)
        if not dm:
            return False

        previous_percentage = dm.current_percentage
        rolled = await self._rollback_manager.execute_rollback(
            dm.deployment, reason, rollback_type,
        )

        if rolled:
            self._metrics.record_rollback(feature_key, rollback_type)
            await self._audit.record_rollback(
                feature_key,
                rollback_type,
                previous_percentage,
                dm.current_percentage,
                reason,
            )

        return rolled

    def record_request(
        self,
        feature_key: str,
        latency_ms: float = 0.0,
        error: bool = False,
        timeout: bool = False,
        exception: bool = False,
    ) -> None:
        """
        Record a request for health monitoring.

        Args:
            feature_key: Feature flag key.
            latency_ms: Request latency.
            error: Whether the request errored.
            timeout: Whether the request timed out.
            exception: Whether an exception occurred.
        """
        dm = self._deployments.get(feature_key)
        if dm:
            dm.record_request(latency_ms, error, timeout, exception)

        self._monitor.record(feature_key, success=not error, latency_ms=latency_ms)
        self._metrics.record_request(feature_key, error=error)

    def check_health(self, feature_key: str) -> Any:
        """
        Check the health of a canary deployment.

        Args:
            feature_key: Feature flag key.

        Returns:
            HealthCheckResult or None.
        """
        dm = self._deployments.get(feature_key)
        if not dm:
            return None
        result = dm.check_health()
        self._metrics.record_health_score(feature_key, result.score)
        return result

    def get_deployment(self, feature_key: str) -> Optional[CanaryDeployment]:
        """Get a deployment by feature key."""
        dm = self._deployments.get(feature_key)
        return dm.deployment if dm else None

    def get_current_percentage(self, feature_key: str) -> float:
        """Get the current percentage for a deployment."""
        dm = self._deployments.get(feature_key)
        return dm.current_percentage if dm else 0.0

    def validate_stages(self, stages: List[CanaryStage]) -> List[str]:
        """Validate deployment stages."""
        return self._validator.validate_stages(stages)

    @property
    def metrics(self) -> CanaryMetrics:
        """Access canary metrics."""
        return self._metrics

    @property
    def audit(self) -> CanaryAudit:
        """Access canary audit."""
        return self._audit

    @property
    def monitor(self) -> CanaryMonitor:
        """Access the real-time monitor."""
        return self._monitor

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            "active_deployments": sum(
                1 for dm in self._deployments.values() if dm.is_running
            ),
            "total_deployments": len(self._deployments),
            "metrics": self._metrics.snapshot(),
            "rollback_stats": self._rollback_manager.get_stats(),
        }
