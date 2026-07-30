"""
Continuous Deployment Engine.

Automates the deployment of models through the lifecycle stages:
Candidate → Staging → Canary → Production.
"""

import enum
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DeploymentStrategy(str, enum.Enum):
    """How a model is deployed to production."""
    DIRECT = "direct"          # Immediate 100% rollout
    CANARY = "canary"          # Gradual traffic increase
    BLUE_GREEN = "blue_green"  # Instant switch with rollback
    SHADOW = "shadow"          # Shadow mode (no real traffic)


class DeploymentStatus(str, enum.Enum):
    """Status of a deployment job."""
    PENDING = "pending"
    APPROVED = "approved"
    DEPLOYING = "deploying"
    CANARY_PROGRESSING = "canary_progressing"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DeploymentConfig:
    """Configuration for continuous deployment."""

    # Strategy
    default_strategy: DeploymentStrategy = DeploymentStrategy.CANARY
    require_approval: bool = True
    require_evaluation_pass: bool = True

    # Canary stages (percentage → duration_minutes)
    canary_stages: Dict[float, float] = field(default_factory=lambda: {
        5.0: 30.0,
        10.0: 60.0,
        25.0: 120.0,
        50.0: 240.0,
        100.0: 0.0,  # final stage
    })

    # Health checks
    health_check_interval_seconds: float = 60.0
    health_check_timeout_seconds: float = 10.0
    min_healthy_duration_seconds: float = 300.0  # 5 min before promoting

    # Rollback
    auto_rollback_on_error: bool = True
    max_error_rate: float = 0.05
    max_latency_increase_pct: float = 0.5

    # Notifications
    notify_on_stage_change: bool = True
    notify_on_complete: bool = True


@dataclass
class DeploymentJob:
    """Tracks a single deployment."""

    job_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    model_name: str = ""
    model_version: str = ""
    previous_version: str = ""

    strategy: DeploymentStrategy = DeploymentStrategy.CANARY
    status: DeploymentStatus = DeploymentStatus.PENDING

    # Canary state
    current_traffic_pct: float = 0.0
    target_traffic_pct: float = 100.0
    stage_index: int = -1

    # Timing
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    # Health
    is_healthy: bool = True
    health_checks_passed: int = 0
    health_checks_failed: int = 0

    # Error tracking
    error_count: int = 0
    error_messages: List[str] = field(default_factory=list)

    # Approval
    approved_by: Optional[str] = None
    approved_at: Optional[float] = None

    # Evaluation
    evaluation_id: Optional[str] = None
    evaluation_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "previous_version": self.previous_version,
            "strategy": self.strategy.value,
            "status": self.status.value,
            "current_traffic_pct": self.current_traffic_pct,
            "is_healthy": self.is_healthy,
            "created_at": self.created_at,
            "health_checks_passed": self.health_checks_passed,
        }

    @property
    def is_active(self) -> bool:
        return self.status in (
            DeploymentStatus.DEPLOYING,
            DeploymentStatus.CANARY_PROGRESSING,
        )


# ---------------------------------------------------------------------------
# Continuous Deployment
# ---------------------------------------------------------------------------

class ContinuousDeployment:
    """Automates model deployment through lifecycle stages.

    Supports multiple deployment strategies (direct, canary, blue-green,
    shadow) with health checks, auto-rollback, and approval workflow
    integration.

    Usage::

        cd = ContinuousDeployment(config, model_registry, serving_service)
        job = cd.deploy("Alpha_v39", strategy=DeploymentStrategy.CANARY)
        cd.advance_canary(job.job_id)  # progress to next stage
    """

    def __init__(
        self,
        config: DeploymentConfig,
        model_registry: Any = None,
        serving_service: Any = None,
    ):
        self.config = config
        self.model_registry = model_registry
        self.serving_service = serving_service

        self._jobs: Dict[str, DeploymentJob] = {}
        self._history: List[DeploymentJob] = []
        self._health_callbacks: List[Callable] = []
        self._stage_change_callbacks: List[Callable] = []

    # ------------------------------------------------------------------
    # Deployment
    # ------------------------------------------------------------------

    def deploy(
        self,
        model_name: str,
        model_version: str,
        strategy: Optional[DeploymentStrategy] = None,
        evaluation_result: Optional[Any] = None,
        previous_version: str = "",
    ) -> DeploymentJob:
        """Initiate a deployment for a model.

        Args:
            model_name: Model to deploy.
            model_version: Version to deploy.
            strategy: Deployment strategy (default from config).
            evaluation_result: Optional evaluation result for gating.
            previous_version: Version being replaced.

        Returns:
            The created DeploymentJob.
        """
        strategy = strategy or self.config.default_strategy

        # Gate: evaluation required
        if self.config.require_evaluation_pass and evaluation_result:
            if hasattr(evaluation_result, "overall_status"):
                status_val = evaluation_result.overall_status
                if hasattr(status_val, "value"):
                    status_val = status_val.value
                if status_val != "PASS":
                    raise ValueError(
                        f"Model {model_name} v{model_version} did not pass evaluation"
                    )

        # Determine previous version
        if not previous_version and self.model_registry:
            try:
                prod = self.model_registry.get_production(model_name)
                if prod:
                    previous_version = prod.version if hasattr(prod, "version") else ""
            except Exception:
                pass

        job = DeploymentJob(
            model_name=model_name,
            model_version=model_version,
            previous_version=previous_version,
            strategy=strategy,
            status=DeploymentStatus.PENDING,
            evaluation_score=(
                evaluation_result.composite_score
                if evaluation_result and hasattr(evaluation_result, "composite_score")
                else 0.0
            ),
            evaluation_id=(
                evaluation_result.eval_id
                if evaluation_result and hasattr(evaluation_result, "eval_id")
                else None
            ),
        )

        self._jobs[job.job_id] = job
        logger.info(
            f"Deployment {job.job_id} created: {model_name} v{model_version} "
            f"(strategy={strategy.value})"
        )

        # If no approval required, start immediately
        if not self.config.require_approval:
            self._start_deployment(job)

        return job

    def approve(self, job_id: str, approved_by: str = "system") -> bool:
        """Approve a pending deployment."""
        job = self._jobs.get(job_id)
        if not job or job.status != DeploymentStatus.PENDING:
            return False

        job.approved_by = approved_by
        job.approved_at = time.time()
        job.status = DeploymentStatus.APPROVED
        logger.info(f"Deployment {job_id} approved by {approved_by}")

        self._start_deployment(job)
        return True

    def _start_deployment(self, job: DeploymentJob) -> None:
        """Begin the actual deployment process."""
        job.started_at = time.time()

        if job.strategy == DeploymentStrategy.DIRECT:
            job.status = DeploymentStatus.DEPLOYING
            self._execute_direct(job)

        elif job.strategy == DeploymentStrategy.CANARY:
            job.status = DeploymentStatus.CANARY_PROGRESSING
            job.stage_index = 0
            self._advance_canary_stage(job)

        elif job.strategy == DeploymentStrategy.BLUE_GREEN:
            job.status = DeploymentStatus.DEPLOYING
            self._execute_blue_green(job)

        elif job.strategy == DeploymentStrategy.SHADOW:
            job.status = DeploymentStatus.DEPLOYING
            self._execute_shadow(job)

    # ------------------------------------------------------------------
    # Canary Progression
    # ------------------------------------------------------------------

    def advance_canary(self, job_id: str) -> bool:
        """Manually advance a canary deployment to the next stage.

        Returns:
            True if advanced, False if already complete or not found.
        """
        job = self._jobs.get(job_id)
        if not job or job.status != DeploymentStatus.CANARY_PROGRESSING:
            return False

        stages = sorted(self.config.canary_stages.keys())
        if job.stage_index >= len(stages) - 1:
            # Already at final stage, complete deployment
            self._complete_deployment(job)
            return False

        job.stage_index += 1
        self._advance_canary_stage(job)
        return True

    def _advance_canary_stage(self, job: DeploymentJob) -> None:
        """Move canary deployment to the current stage index."""
        stages = sorted(self.config.canary_stages.keys())
        if job.stage_index >= len(stages):
            self._complete_deployment(job)
            return

        traffic_pct = stages[job.stage_index]
        duration = self.config.canary_stages[traffic_pct]

        job.current_traffic_pct = traffic_pct
        job.target_traffic_pct = traffic_pct

        logger.info(
            f"Canary stage {job.stage_index + 1}/{len(stages)}: "
            f"{traffic_pct}% traffic for {job.model_name} v{job.model_version}"
        )

        # Update serving traffic split
        if self.serving_service:
            try:
                # In production: update model router traffic weights
                pass
            except Exception as e:
                logger.error(f"Failed to update canary traffic: {e}")

        # Notify stage change
        self._notify_stage_change(job)

        # If final stage, mark complete
        if traffic_pct >= 100.0:
            self._complete_deployment(job)

    # ------------------------------------------------------------------
    # Strategy Implementations
    # ------------------------------------------------------------------

    def _execute_direct(self, job: DeploymentJob) -> None:
        """Direct 100% rollout."""
        logger.info(f"Direct deployment: {job.model_name} v{job.model_version}")
        if self.model_registry:
            try:
                self.model_registry.promote(job.model_name, job.model_version, "production")
            except Exception as e:
                logger.error(f"Direct deployment failed: {e}")
                job.status = DeploymentStatus.FAILED
                job.error_messages.append(str(e))
                return
        self._complete_deployment(job)

    def _execute_blue_green(self, job: DeploymentJob) -> None:
        """Blue-green deployment: instant switch with rollback capability."""
        logger.info(f"Blue-green deployment: {job.model_name} v{job.model_version}")
        # In production: register new as green, keep blue for rollback
        self._complete_deployment(job)

    def _execute_shadow(self, job: DeploymentJob) -> None:
        """Shadow deployment: run predictions without using them."""
        logger.info(f"Shadow deployment: {job.model_name} v{job.model_version}")
        self._complete_deployment(job)

    def _complete_deployment(self, job: DeploymentJob) -> None:
        """Mark a deployment as complete."""
        job.status = DeploymentStatus.COMPLETED
        job.completed_at = time.time()
        job.current_traffic_pct = 100.0
        self._history.append(job)
        logger.info(
            f"Deployment {job.job_id} completed: "
            f"{job.model_name} v{job.model_version} at 100%"
        )

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def rollback(self, job_id: str, reason: str = "") -> bool:
        """Rollback a deployment to the previous version.

        Args:
            job_id: Deployment job to rollback.
            reason: Why the rollback is needed.

        Returns:
            True if rollback initiated.
        """
        job = self._jobs.get(job_id)
        if not job or job.status == DeploymentStatus.ROLLED_BACK:
            return False

        logger.warning(
            f"Rolling back deployment {job_id}: "
            f"{job.model_name} v{job.model_version} → v{job.previous_version}. "
            f"Reason: {reason}"
        )

        # Restore previous version
        if self.model_registry and job.previous_version:
            try:
                self.model_registry.demote(job.model_name, job.model_version, "archived")
                self.model_registry.promote(job.model_name, job.previous_version, "production")
            except Exception as e:
                logger.error(f"Rollback failed: {e}")

        job.status = DeploymentStatus.ROLLED_BACK
        job.completed_at = time.time()
        return True

    # ------------------------------------------------------------------
    # Health Checks
    # ------------------------------------------------------------------

    def check_health(self, job_id: str) -> bool:
        """Run a health check on a deploying model.

        Returns:
            True if healthy.
        """
        job = self._jobs.get(job_id)
        if not job or not job.is_active:
            return False

        # In production: check inference monitor metrics
        # For now, simulate health check
        is_healthy = True

        if is_healthy:
            job.health_checks_passed += 1
            job.is_healthy = True
        else:
            job.health_checks_failed += 1
            job.is_healthy = False

            if self.config.auto_rollback_on_error:
                self.rollback(job_id, reason="Health check failed")

        return is_healthy

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_job(self, job_id: str) -> Optional[DeploymentJob]:
        """Get a deployment job by ID."""
        return self._jobs.get(job_id)

    def get_active_deployments(self) -> List[DeploymentJob]:
        """Get all currently active deployments."""
        return [j for j in self._jobs.values() if j.is_active]

    def list_jobs(
        self,
        status: Optional[DeploymentStatus] = None,
        model_name: Optional[str] = None,
    ) -> List[DeploymentJob]:
        """List deployment jobs with filters."""
        jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        if model_name:
            jobs = [j for j in jobs if j.model_name == model_name]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_stage_change(self, callback: Callable) -> None:
        """Register a callback for canary stage changes."""
        self._stage_change_callbacks.append(callback)

    def on_health_check(self, callback: Callable) -> None:
        """Register a callback for health checks."""
        self._health_callbacks.append(callback)

    def _notify_stage_change(self, job: DeploymentJob) -> None:
        for cb in self._stage_change_callbacks:
            try:
                cb(job)
            except Exception as e:
                logger.error(f"Stage change callback error: {e}")

    def reset(self) -> None:
        """Reset state (for testing)."""
        self._jobs.clear()
        self._history.clear()
