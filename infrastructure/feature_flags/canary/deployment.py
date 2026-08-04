"""
Canary deployment management.

Manages the lifecycle of a canary deployment
including stage progression, health checks,
and status tracking.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .health import HealthMonitor, HealthStatus
from .policy import CanaryPolicy
from .stage import CanaryDeployment, CanaryStage, DEFAULT_CANARY_STAGES


class CanaryDeploymentManager:
    """
    Manages canary deployment lifecycle.

    Controls stage progression with health
    checks at each stage boundary.

    Usage:
        dm = CanaryDeploymentManager(
            deployment=CanaryDeployment(feature_key="new-risk"),
            policy=CanaryPolicy(),
        )
        await dm.start()
        # Health checks happen automatically
        # Promote to next stage when healthy
        promoted = await dm.promote()
    """

    def __init__(
        self,
        deployment: Optional[CanaryDeployment] = None,
        policy: Optional[CanaryPolicy] = None,
    ) -> None:
        """
        Initialize the deployment manager.

        Args:
            deployment: Canary deployment to manage.
            policy: Deployment policy.
        """
        self._deployment = deployment or CanaryDeployment()
        self._policy = policy or CanaryPolicy()
        self._health_monitor = HealthMonitor()
        self._stage_start_time: Optional[float] = None
        self._promotion_count = 0
        self._rollback_count = 0

    async def start(self) -> None:
        """Start the canary deployment."""
        self._deployment.status = "running"
        self._deployment.started_at = time.time()
        self._stage_start_time = time.time()
        self._health_monitor.start()

    async def promote(self, force: bool = False) -> bool:
        """
        Promote to the next deployment stage.

        Args:
            force: Force promotion regardless of health.

        Returns:
            True if promoted successfully.
        """
        if self._deployment.status != "running":
            return False

        if self._deployment.current_stage_index >= len(self._deployment.stages) - 1:
            return False

        if not force:
            # Check health before promotion
            stage = self._deployment.current_stage
            if self._policy.auto_promote and not stage.auto_promote:
                return False

            # Check minimum sample size
            stats = self._health_monitor.get_stats()
            if stats["request_count"] < self._policy.min_sample_size:
                return False

            # Check health
            health = self._health_monitor.check_health(
                error_rate_threshold=stage.error_rate_threshold,
                latency_p99_threshold_ms=stage.latency_p99_threshold_ms,
                health_threshold=stage.health_threshold,
            )
            if health.status == HealthStatus.CRITICAL:
                if self._policy.rollback_on_failure:
                    await self.rollback()
                    return False
                return False

            if health.status != HealthStatus.HEALTHY:
                return False

            # Check duration
            if self._stage_start_time:
                elapsed = time.time() - self._stage_start_time
                if elapsed < self._deployment.current_stage.duration.total_seconds():
                    return False

        self._deployment.current_stage_index += 1
        self._stage_start_time = time.time()
        self._health_monitor.start()
        self._promotion_count += 1

        # Check if complete
        if self._deployment.is_complete:
            self._deployment.status = "completed"
            self._deployment.completed_at = time.time()

        return True

    async def rollback(self, reason: str = "") -> bool:
        """
        Rollback to the previous stage.

        Args:
            reason: Reason for rollback.

        Returns:
            True if rolled back.
        """
        if self._deployment.current_stage_index <= 0:
            self._deployment.status = "rolled_back"
            return False

        self._deployment.current_stage_index -= 1
        self._deployment.status = "running"
        self._stage_start_time = time.time()
        self._health_monitor.start()
        self._rollback_count += 1
        return True

    async def emergency_rollback(self) -> bool:
        """
        Emergency rollback to 0% traffic.

        Returns:
            True if rolled back.
        """
        self._deployment.current_stage_index = 0
        self._deployment.status = "rolled_back"
        self._deployment.completed_at = time.time()
        self._rollback_count += 1
        return True

    def record_request(
        self,
        latency_ms: float = 0.0,
        error: bool = False,
        timeout: bool = False,
        exception: bool = False,
    ) -> None:
        """Record a request for health monitoring."""
        self._health_monitor.record_request(
            latency_ms=latency_ms,
            error=error,
            timeout=timeout,
            exception=exception,
        )

    def check_health(self) -> "HealthCheckResult":
        """Check the current health status."""
        from .health import HealthCheckResult

        stage = self._deployment.current_stage
        return self._health_monitor.check_health(
            error_rate_threshold=stage.error_rate_threshold,
            latency_p99_threshold_ms=stage.latency_p99_threshold_ms,
            health_threshold=stage.health_threshold,
        )

    @property
    def deployment(self) -> CanaryDeployment:
        """Get the deployment."""
        return self._deployment

    @property
    def current_percentage(self) -> float:
        """Get the current traffic percentage."""
        return self._deployment.current_percentage

    @property
    def is_running(self) -> bool:
        """Check if the deployment is active."""
        return self._deployment.status == "running"

    def get_stats(self) -> Dict[str, Any]:
        """Get deployment statistics."""
        return {
            "deployment_id": self._deployment.deployment_id,
            "feature_key": self._deployment.feature_key,
            "status": self._deployment.status,
            "current_stage_index": self._deployment.current_stage_index,
            "current_percentage": self._deployment.current_percentage,
            "progress": self._deployment.progress,
            "promotions": self._promotion_count,
            "rollbacks": self._rollback_count,
            "health": self._health_monitor.get_stats(),
        }
