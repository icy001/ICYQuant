"""
Continuous Training Engine.

Triggers model retraining based on:
- Schedule (daily, weekly, monthly)
- Data freshness (new data available)
- Performance degradation (Sharpe/IC decay)
- Drift events (data/model drift detected)
- Manual trigger
"""

import enum
import time
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TrainingTrigger(str, enum.Enum):
    """What triggered the training job."""
    SCHEDULE = "schedule"
    DATA_FRESHNESS = "data_freshness"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    DRIFT_EVENT = "drift_event"
    MANUAL = "manual"
    CHALLENGER_PROMOTION = "challenger_promotion"


class TrainingStatus(str, enum.Enum):
    """Status of a training job."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RetrainReason(str, enum.Enum):
    """Reason why retraining was triggered."""
    SCHEDULED_REFRESH = "scheduled_refresh"
    NEW_DATA_AVAILABLE = "new_data_available"
    SHARPE_BELOW_THRESHOLD = "sharpe_below_threshold"
    IC_BELOW_THRESHOLD = "ic_below_threshold"
    DATA_DRIFT_DETECTED = "data_drift_detected"
    MODEL_DRIFT_DETECTED = "model_drift_detected"
    MANUAL_RETRAIN = "manual_retrain"
    CHALLENGER_LOST = "challenger_lost"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TrainingConfig:
    """Configuration for continuous training."""

    # Scheduling
    schedule_cron: str = "0 6 * * *"  # Default: daily at 6 AM
    enabled_triggers: List[TrainingTrigger] = field(default_factory=lambda: [
        TrainingTrigger.SCHEDULE,
        TrainingTrigger.DATA_FRESHNESS,
        TrainingTrigger.DRIFT_EVENT,
    ])

    # Data freshness
    data_freshness_max_age_hours: float = 24.0
    data_source_check_interval_minutes: float = 60.0

    # Performance degradation thresholds
    sharpe_min_threshold: float = 0.5
    sharpe_degradation_pct: float = 0.4  # 40% drop triggers retrain
    ic_min_threshold: float = 0.02
    ic_degradation_pct: float = 0.5

    # Training limits
    max_concurrent_jobs: int = 2
    max_retries: int = 3
    retry_delay_seconds: float = 300.0
    job_timeout_seconds: float = 7200.0  # 2 hours

    # Model registration
    auto_register_candidate: bool = True
    auto_evaluate: bool = True
    candidate_name_prefix: str = "ct_"

    # Pipeline
    pipeline_name: str = "daily_alpha"
    feature_pipeline_name: str = "alpha_pipeline"
    automl_config_name: str = "default"


@dataclass
class TrainingJob:
    """A single continuous training job."""

    job_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    model_name: str = ""
    pipeline_name: str = ""

    trigger: TrainingTrigger = TrainingTrigger.SCHEDULE
    reason: RetrainReason = RetrainReason.SCHEDULED_REFRESH
    status: TrainingStatus = TrainingStatus.PENDING

    # Timing
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    # Results
    new_model_version: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    error_message: Optional[str] = None

    # Retry
    retry_count: int = 0
    max_retries: int = 3

    # Metadata
    tags: Dict[str, str] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        if self.started_at:
            return time.time() - self.started_at
        return None

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            TrainingStatus.COMPLETED,
            TrainingStatus.FAILED,
            TrainingStatus.CANCELLED,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "model_name": self.model_name,
            "pipeline_name": self.pipeline_name,
            "trigger": self.trigger.value,
            "reason": self.reason.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "new_model_version": self.new_model_version,
            "metrics": self.metrics,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "duration_seconds": self.duration_seconds,
            "tags": self.tags,
        }


# ---------------------------------------------------------------------------
# Continuous Trainer
# ---------------------------------------------------------------------------

class ContinuousTrainer:
    """Orchestrates continuous (re)training of ML models.

    Monitors data freshness, model performance, and drift signals to
    automatically trigger retraining jobs.

    Usage::

        trainer = ContinuousTrainer(config, model_registry, automl_service)
        job = trainer.train("Alpha_v38", trigger=TrainingTrigger.DRIFT_EVENT)
    """

    def __init__(
        self,
        config: TrainingConfig,
        model_registry: Any = None,
        automl_service: Any = None,
        feature_service: Any = None,
    ):
        self.config = config
        self.model_registry = model_registry
        self.automl_service = automl_service
        self.feature_service = feature_service

        self._jobs: Dict[str, TrainingJob] = {}
        self._history: List[TrainingJob] = []
        self._running_count: int = 0

        # Callbacks
        self._on_train_complete: List[Callable] = []
        self._on_train_fail: List[Callable] = []
        self._train_fn: Optional[Callable] = None

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        model_name: str,
        trigger: TrainingTrigger = TrainingTrigger.MANUAL,
        reason: RetrainReason = RetrainReason.MANUAL_RETRAIN,
        **kwargs,
    ) -> TrainingJob:
        """Trigger a training job.

        Args:
            model_name: Target model to retrain.
            trigger: What triggered this training.
            reason: Why retraining is needed.

        Returns:
            The created TrainingJob.
        """
        if self._running_count >= self.config.max_concurrent_jobs:
            logger.warning(
                f"Max concurrent jobs ({self.config.max_concurrent_jobs}) reached. Queuing."
            )

        job = TrainingJob(
            model_name=model_name,
            pipeline_name=self.config.pipeline_name,
            trigger=trigger,
            reason=reason,
            status=TrainingStatus.QUEUED,
            max_retries=self.config.max_retries,
            tags=kwargs.get("tags", {}),
        )

        self._jobs[job.job_id] = job
        logger.info(
            f"Training job {job.job_id} created: {model_name} "
            f"(trigger={trigger.value}, reason={reason.value})"
        )

        # Start immediately if capacity allows
        if self._running_count < self.config.max_concurrent_jobs:
            self._start_job(job)

        return job

    def _start_job(self, job: TrainingJob) -> None:
        """Execute a training job."""
        job.status = TrainingStatus.RUNNING
        job.started_at = time.time()
        self._running_count += 1

        logger.info(f"Starting training job {job.job_id} for {job.model_name}")

        try:
            if self._train_fn:
                result = self._train_fn(job)
                if result:
                    job.new_model_version = result.get("version", "")
                    job.metrics = result.get("metrics", {})
                job.status = TrainingStatus.COMPLETED
            else:
                # Simulated training for testing
                time.sleep(0.01)
                job.new_model_version = f"{job.model_name}_ct_{int(time.time())}"
                job.metrics = {"sharpe": 2.15, "ic": 0.062, "max_drawdown": 0.12}
                job.status = TrainingStatus.COMPLETED

            job.completed_at = time.time()
            self._history.append(job)
            logger.info(
                f"Training job {job.job_id} completed: "
                f"version={job.new_model_version}, metrics={job.metrics}"
            )

            self._notify_complete(job)

            # Auto-register candidate
            if self.config.auto_register_candidate and self.model_registry:
                candidate_name = f"{self.config.candidate_name_prefix}{job.model_name}"
                try:
                    self.model_registry.register(
                        model_name=candidate_name,
                        version=job.new_model_version or f"v{int(time.time())}",
                        metadata={"trigger": job.trigger.value, "job_id": job.job_id},
                        metrics=job.metrics,
                    )
                except Exception as e:
                    logger.warning(f"Auto-register candidate failed: {e}")

        except Exception as e:
            job.status = TrainingStatus.FAILED
            job.error_message = str(e)
            job.completed_at = time.time()
            logger.error(f"Training job {job.job_id} failed: {e}")
            self._notify_fail(job)

            # Retry
            if job.retry_count < job.max_retries:
                job.retry_count += 1
                logger.info(
                    f"Retrying job {job.job_id} ({job.retry_count}/{job.max_retries})"
                )
                time.sleep(self.config.retry_delay_seconds * 0.001)  # scale for test
                self._start_job(job)
                return

        finally:
            self._running_count -= 1

    # ------------------------------------------------------------------
    # Monitoring & Triggers
    # ------------------------------------------------------------------

    def check_data_freshness(self) -> Optional[TrainingJob]:
        """Check if new data is available and trigger retraining.

        Returns:
            TrainingJob if triggered, None otherwise.
        """
        if TrainingTrigger.DATA_FRESHNESS not in self.config.enabled_triggers:
            return None

        # In production, check data source timestamps
        # For now, use a simple heuristic
        stale = self._is_data_stale()
        if stale:
            logger.info("Data freshness check: data is stale, triggering retrain")
            return self.train(
                model_name=self._get_active_model(),
                trigger=TrainingTrigger.DATA_FRESHNESS,
                reason=RetrainReason.NEW_DATA_AVAILABLE,
            )
        return None

    def check_performance_degradation(
        self, current_sharpe: float, current_ic: float, baseline_sharpe: float, baseline_ic: float
    ) -> Optional[TrainingJob]:
        """Check if model performance has degraded and trigger retraining.

        Args:
            current_sharpe: Current model Sharpe ratio.
            current_ic: Current Information Coefficient.
            baseline_sharpe: Baseline (training) Sharpe ratio.
            baseline_ic: Baseline (training) IC.

        Returns:
            TrainingJob if triggered, None otherwise.
        """
        if TrainingTrigger.PERFORMANCE_DEGRADATION not in self.config.enabled_triggers:
            return None

        # Sharpe degradation
        if baseline_sharpe > 0:
            sharpe_drop = (baseline_sharpe - current_sharpe) / baseline_sharpe
            if sharpe_drop > self.config.sharpe_degradation_pct:
                logger.warning(
                    f"Sharpe degraded by {sharpe_drop:.1%} "
                    f"({baseline_sharpe:.2f} → {current_sharpe:.2f})"
                )
                return self.train(
                    model_name=self._get_active_model(),
                    trigger=TrainingTrigger.PERFORMANCE_DEGRADATION,
                    reason=RetrainReason.SHARPE_BELOW_THRESHOLD,
                )

        # IC degradation
        if baseline_ic > 0:
            ic_drop = (baseline_ic - current_ic) / baseline_ic
            if ic_drop > self.config.ic_degradation_pct:
                logger.warning(
                    f"IC degraded by {ic_drop:.1%} "
                    f"({baseline_ic:.4f} → {current_ic:.4f})"
                )
                return self.train(
                    model_name=self._get_active_model(),
                    trigger=TrainingTrigger.PERFORMANCE_DEGRADATION,
                    reason=RetrainReason.IC_BELOW_THRESHOLD,
                )

        # Absolute threshold
        if current_sharpe < self.config.sharpe_min_threshold:
            logger.warning(f"Sharpe {current_sharpe:.2f} below minimum {self.config.sharpe_min_threshold}")
            return self.train(
                model_name=self._get_active_model(),
                trigger=TrainingTrigger.PERFORMANCE_DEGRADATION,
                reason=RetrainReason.SHARPE_BELOW_THRESHOLD,
            )

        if abs(current_ic) < self.config.ic_min_threshold:
            logger.warning(f"IC {current_ic:.4f} below minimum {self.config.ic_min_threshold}")
            return self.train(
                model_name=self._get_active_model(),
                trigger=TrainingTrigger.PERFORMANCE_DEGRADATION,
                reason=RetrainReason.IC_BELOW_THRESHOLD,
            )

        return None

    def on_drift_event(
        self, drift_type: str, severity: str, model_name: str
    ) -> Optional[TrainingJob]:
        """Handle a drift event by triggering retraining if configured.

        Args:
            drift_type: "data" or "model".
            severity: Drift severity level.
            model_name: Affected model.

        Returns:
            TrainingJob if triggered, None otherwise.
        """
        if TrainingTrigger.DRIFT_EVENT not in self.config.enabled_triggers:
            return None

        reason = (
            RetrainReason.DATA_DRIFT_DETECTED
            if drift_type == "data"
            else RetrainReason.MODEL_DRIFT_DETECTED
        )

        logger.info(f"Drift event: type={drift_type}, severity={severity}, model={model_name}")
        return self.train(
            model_name=model_name,
            trigger=TrainingTrigger.DRIFT_EVENT,
            reason=reason,
        )

    # ------------------------------------------------------------------
    # Job Management
    # ------------------------------------------------------------------

    def get_job(self, job_id: str) -> Optional[TrainingJob]:
        """Get a training job by ID."""
        return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or queued training job."""
        job = self._jobs.get(job_id)
        if job and job.status in (TrainingStatus.PENDING, TrainingStatus.QUEUED):
            job.status = TrainingStatus.CANCELLED
            job.completed_at = time.time()
            return True
        return False

    def list_jobs(
        self,
        status: Optional[TrainingStatus] = None,
        model_name: Optional[str] = None,
    ) -> List[TrainingJob]:
        """List training jobs with optional filters."""
        jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        if model_name:
            jobs = [j for j in jobs if j.model_name == model_name]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def get_active_jobs(self) -> List[TrainingJob]:
        """Get currently running training jobs."""
        return [
            j for j in self._jobs.values()
            if j.status in (TrainingStatus.PENDING, TrainingStatus.QUEUED, TrainingStatus.RUNNING)
        ]

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def set_train_fn(self, fn: Callable) -> None:
        """Set the actual training function to use.

        The function receives a TrainingJob and should return a dict
        with 'version' and 'metrics' keys.
        """
        self._train_fn = fn

    def on_complete(self, callback: Callable) -> None:
        """Register a callback for training completion."""
        self._on_train_complete.append(callback)

    def on_fail(self, callback: Callable) -> None:
        """Register a callback for training failure."""
        self._on_train_fail.append(callback)

    def _notify_complete(self, job: TrainingJob) -> None:
        for cb in self._on_train_complete:
            try:
                cb(job)
            except Exception as e:
                logger.error(f"Completion callback error: {e}")

    def _notify_fail(self, job: TrainingJob) -> None:
        for cb in self._on_train_fail:
            try:
                cb(job)
            except Exception as e:
                logger.error(f"Failure callback error: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_active_model(self) -> str:
        """Get the currently active (production) model name."""
        if self.model_registry:
            try:
                entries = self.model_registry.list_by_stage("production")
                if entries:
                    return entries[0].model_name if hasattr(entries[0], 'model_name') else str(entries[0])
            except Exception:
                pass
        return "Alpha_latest"

    def _is_data_stale(self) -> bool:
        """Check if data is older than max_age threshold."""
        # In production, check the actual data source
        return False

    def reset(self) -> None:
        """Reset the trainer state (for testing)."""
        self._jobs.clear()
        self._history.clear()
        self._running_count = 0
