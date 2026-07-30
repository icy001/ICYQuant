"""
MLOps Service — Unified Orchestrator.

Top-level service that orchestrates all MLOps components:
- ContinuousTraining, ContinuousEvaluation, ContinuousDeployment
- DriftDetector, ChampionChallenger, RollbackManager
- LifecycleManager, ApprovalManager, MLOpsScheduler

Provides a single entry point for the complete MLOps pipeline:
    Data → Train → Evaluate → Approve → Deploy → Monitor → Retrain
"""

import enum
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.mlops.trainer import (
    ContinuousTrainer, TrainingConfig, TrainingJob, TrainingTrigger, RetrainReason,
)
from services.mlops.evaluator import (
    ContinuousEvaluator, EvaluationConfig, EvaluationResult, GateStatus,
)
from services.mlops.deployment import (
    ContinuousDeployment, DeploymentConfig, DeploymentStrategy, DeploymentJob,
)
from services.mlops.drift_detector import (
    DriftDetector, DriftConfig, DriftReport, DriftSeverity,
)
from services.mlops.champion_challenger import (
    ChampionChallenger, CCConfig, CCResult, PromotionDecision,
)
from services.mlops.rollback import (
    RollbackManager, RollbackConfig, RollbackEvent, RollbackStatus,
)
from services.mlops.lifecycle import (
    LifecycleManager, LifecycleConfig, LifecycleStage, LifecycleRecord,
)
from services.mlops.scheduler import (
    MLOpsScheduler, SchedulerConfig, ScheduleEntry,
)
from services.mlops.approval import (
    ApprovalManager, ApprovalConfig, ApprovalRequest, ApprovalStatus,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PipelineStatus(str, enum.Enum):
    """Status of an MLOps pipeline run."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PipelineRun:
    """Tracks a full MLOps pipeline execution."""

    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    model_name: str = ""
    status: PipelineStatus = PipelineStatus.IDLE

    # Stages
    training_job_id: Optional[str] = None
    evaluation_result_id: Optional[str] = None
    approval_request_id: Optional[str] = None
    deployment_job_id: Optional[str] = None

    # Timing
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    # Results
    new_model_version: Optional[str] = None
    evaluation_score: float = 0.0
    deployed: bool = False

    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "model_name": self.model_name,
            "status": self.status.value,
            "new_model_version": self.new_model_version,
            "evaluation_score": self.evaluation_score,
            "deployed": self.deployed,
            "started_at": self.started_at,
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# MLOps Config
# ---------------------------------------------------------------------------

@dataclass
class MLOpsConfig:
    """Master configuration for the MLOps service."""

    # Sub-component configs
    training: TrainingConfig = field(default_factory=TrainingConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)
    deployment: DeploymentConfig = field(default_factory=DeploymentConfig)
    drift: DriftConfig = field(default_factory=DriftConfig)
    champion: CCConfig = field(default_factory=CCConfig)
    rollback: RollbackConfig = field(default_factory=RollbackConfig)
    lifecycle: LifecycleConfig = field(default_factory=LifecycleConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    approval: ApprovalConfig = field(default_factory=ApprovalConfig)

    # Pipeline mode
    auto_pipeline: bool = False  # Fully automated end-to-end

    # Monitoring
    monitor_interval_seconds: float = 300.0  # 5 min


# ---------------------------------------------------------------------------
# MLOps Service
# ---------------------------------------------------------------------------

class MLOpsService:
    """Unified MLOps orchestration service.

    Wires together all MLOps components into a cohesive platform:
    - Continuous Training → Evaluation → Approval → Deployment
    - Drift Detection → Retraining trigger
    - Champion/Challenger → Auto-promotion
    - Rollback → Safety net
    - Lifecycle → Audit trail

    Usage::

        mlops = MLOpsService(config)
        mlops.run_pipeline("Alpha_v38")

        # Or step-by-step:
        job = mlops.train("Alpha_v38")
        result = mlops.evaluate(job.new_model_version, metrics)
        if result.overall_status == GateStatus.PASS:
            mlops.deploy("Alpha_v38", job.new_model_version)
    """

    def __init__(
        self,
        config: MLOpsConfig,
        model_registry: Any = None,
        automl_service: Any = None,
        feature_service: Any = None,
        serving_service: Any = None,
    ):
        self.config = config
        self.model_registry = model_registry
        self.automl_service = automl_service
        self.feature_service = feature_service
        self.serving_service = serving_service

        # Initialize sub-components
        self.trainer = ContinuousTrainer(
            config.training, model_registry, automl_service, feature_service,
        )
        self.evaluator = ContinuousEvaluator(config.evaluation)
        self.deployer = ContinuousDeployment(
            config.deployment, model_registry, serving_service,
        )
        self.drift_detector = DriftDetector(config.drift)
        self.champion_challenger = ChampionChallenger(config.champion)
        self.rollback_manager = RollbackManager(
            config.rollback, model_registry, self.deployer,
        )
        self.lifecycle = LifecycleManager(config.lifecycle)
        self.scheduler = MLOpsScheduler(config.scheduler)
        self.approval = ApprovalManager(config.approval)

        # Pipeline tracking
        self._pipeline_runs: Dict[str, PipelineRun] = {}
        self._pipeline_history: List[PipelineRun] = []

        # Wire up cross-component callbacks
        self._wire_callbacks()

    def _wire_callbacks(self) -> None:
        """Wire up internal callbacks between components."""
        # Drift → Trainer
        def on_drift(report: DriftReport):
            if report.requires_retraining:
                self.trainer.on_drift_event(
                    drift_type="data" if report.any_data_drift else "model",
                    severity=(
                        report.data_drift_severity.value
                        if report.any_data_drift
                        else report.model_drift_severity.value
                    ),
                    model_name=report.model_name,
                )

        self.drift_detector.on_drift(on_drift)

        # Trainer complete → Evaluate
        def on_train_complete(job: TrainingJob):
            if self.config.evaluation.auto_promote_on_pass and job.metrics:
                result = self.evaluator.evaluate(
                    model_name=job.model_name,
                    model_version=job.new_model_version or "unknown",
                    metrics=job.metrics,
                )
                if result.overall_status == GateStatus.PASS:
                    logger.info(
                        f"Auto-deploy triggered for {job.model_name} "
                        f"v{job.new_model_version}"
                    )
                    self.deployer.deploy(
                        model_name=job.model_name,
                        model_version=job.new_model_version or "unknown",
                        evaluation_result=result,
                    )

        self.trainer.on_complete(on_train_complete)

    # ------------------------------------------------------------------
    # Pipeline Operations
    # ------------------------------------------------------------------

    def run_pipeline(
        self,
        model_name: str,
        trigger: TrainingTrigger = TrainingTrigger.MANUAL,
    ) -> PipelineRun:
        """Run a complete MLOps pipeline end-to-end.

        Pipeline stages:
        1. Train → 2. Evaluate → 3. Approve → 4. Deploy

        Args:
            model_name: Model to process.
            trigger: What triggered the pipeline.

        Returns:
            PipelineRun tracking the execution.
        """
        run = PipelineRun(model_name=model_name, status=PipelineStatus.RUNNING)
        self._pipeline_runs[run.run_id] = run

        logger.info(f"Starting pipeline {run.run_id} for {model_name}")

        try:
            # Stage 1: Training
            job = self.trainer.train(
                model_name=model_name,
                trigger=trigger,
                reason=RetrainReason.SCHEDULED_REFRESH,
            )
            run.training_job_id = job.job_id

            if job.status.value == "failed":
                run.status = PipelineStatus.FAILED
                run.errors.append(f"Training failed: {job.error_message}")
                return run

            new_version = job.new_model_version or f"v{int(time.time())}"
            run.new_model_version = new_version

            # Stage 2: Evaluation
            result = self.evaluator.evaluate(
                model_name=model_name,
                model_version=new_version,
                metrics=job.metrics,
            )
            run.evaluation_result_id = result.eval_id
            run.evaluation_score = result.composite_score

            if result.overall_status == GateStatus.FAIL:
                run.status = PipelineStatus.FAILED
                run.errors.append(f"Evaluation failed: {result.recommendation}")
                return run

            # Stage 3: Approval
            if self.config.approval.require_risk_review:
                req = self.approval.submit(
                    model_name=model_name,
                    model_version=new_version,
                    requested_by="mlops_pipeline",
                    evaluation_score=result.composite_score,
                    evaluation_id=result.eval_id,
                    metrics_summary=result.metrics,
                )
                run.approval_request_id = req.request_id

            # Stage 4: Deployment
            dep_job = self.deployer.deploy(
                model_name=model_name,
                model_version=new_version,
                evaluation_result=result,
            )
            run.deployment_job_id = dep_job.job_id
            run.deployed = True

            run.status = PipelineStatus.COMPLETED
            run.completed_at = time.time()

            logger.info(
                f"Pipeline {run.run_id} completed: "
                f"{model_name} v{new_version} deployed"
            )

        except Exception as e:
            run.status = PipelineStatus.FAILED
            run.errors.append(str(e))
            logger.error(f"Pipeline {run.run_id} failed: {e}")

        finally:
            self._pipeline_history.append(run)

        return run

    # ------------------------------------------------------------------
    # Component Delegation
    # ------------------------------------------------------------------

    def train(
        self,
        model_name: str,
        trigger: TrainingTrigger = TrainingTrigger.MANUAL,
    ) -> TrainingJob:
        """Trigger a training job (delegates to ContinuousTrainer)."""
        return self.trainer.train(model_name=model_name, trigger=trigger)

    def evaluate(
        self, model_name: str, model_version: str, metrics: Dict[str, float]
    ) -> EvaluationResult:
        """Evaluate a model (delegates to ContinuousEvaluator)."""
        return self.evaluator.evaluate(model_name, model_version, metrics)

    def deploy(
        self,
        model_name: str,
        model_version: str,
        strategy: Optional[DeploymentStrategy] = None,
    ) -> DeploymentJob:
        """Deploy a model (delegates to ContinuousDeployment)."""
        return self.deployer.deploy(
            model_name=model_name,
            model_version=model_version,
            strategy=strategy,
        )

    def check_drift(
        self,
        model_name: str,
        current_features: Dict[str, List[float]],
        current_predictions: Optional[List[float]] = None,
    ) -> DriftReport:
        """Check for drift (delegates to DriftDetector)."""
        return self.drift_detector.check_drift(
            model_name, current_features, current_predictions,
        )

    def evaluate_champion(self) -> List[CCResult]:
        """Evaluate champion vs challengers (delegates to ChampionChallenger)."""
        return self.champion_challenger.evaluate()

    def check_rollback(
        self, model_name: str, metrics: Dict[str, float]
    ) -> List[RollbackEvent]:
        """Check rollback conditions (delegates to RollbackManager)."""
        return self.rollback_manager.check_all_metrics(model_name, metrics)

    # ------------------------------------------------------------------
    # Monitoring Loop
    # ------------------------------------------------------------------

    def monitor_loop_iteration(self, model_name: str) -> Dict[str, Any]:
        """Run one iteration of the monitoring loop.

        Checks drift, performance, and rollback conditions for a model.

        Returns:
            Dict with monitoring results.
        """
        results = {
            "model": model_name,
            "timestamp": time.time(),
            "drift": None,
            "rollback_triggered": False,
        }

        # Drift check
        report = self.drift_detector.get_latest_report(model_name)
        results["drift"] = report.to_dict() if report else None

        # Rollback check
        if report and report.requires_rollback:
            event = self.rollback_manager.rollback(
                model_name=model_name,
                reason=f"Drift detected: {report.summary}",
            )
            if event:
                results["rollback_triggered"] = True
                results["rollback_event"] = event.to_dict()

        return results

    # ------------------------------------------------------------------
    # Health & Status
    # ------------------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Get overall MLOps platform health."""
        return {
            "status": "healthy",
            "components": {
                "trainer": {
                    "active_jobs": len(self.trainer.get_active_jobs()),
                    "total_jobs": len(self.trainer.list_jobs()),
                },
                "deployer": {
                    "active_deployments": len(self.deployer.get_active_deployments()),
                },
                "approval": {
                    "pending": self.approval.get_pending_count(),
                },
                "champion": self.champion_challenger.get_status(),
                "lifecycle": self.lifecycle.get_statistics(),
            },
            "pipeline_runs": len(self._pipeline_history),
            "timestamp": time.time(),
        }

    def get_pipeline_run(self, run_id: str) -> Optional[PipelineRun]:
        """Get a pipeline run by ID."""
        return self._pipeline_runs.get(run_id)

    def get_pipeline_history(self, limit: int = 50) -> List[PipelineRun]:
        """Get pipeline run history."""
        return sorted(
            self._pipeline_history,
            key=lambda r: r.started_at,
            reverse=True,
        )[:limit]

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def setup_default_schedules(self, model_name: str) -> List[ScheduleEntry]:
        """Set up default monitoring schedules for a model.

        Args:
            model_name: Model to schedule for.

        Returns:
            List of created ScheduleEntry objects.
        """
        entries = []

        entries.append(
            self.scheduler.schedule_training(
                model_name,
                interval_hours=self.config.scheduler.default_training_interval_hours,
            )
        )
        entries.append(
            self.scheduler.schedule_evaluation(
                model_name,
                interval_hours=self.config.scheduler.default_evaluation_interval_hours,
            )
        )
        entries.append(
            self.scheduler.schedule_drift_check(
                model_name,
                interval_hours=self.config.scheduler.default_drift_check_interval_hours,
            )
        )
        entries.append(
            self.scheduler.schedule_champion_check(
                model_name,
                interval_hours=self.config.scheduler.default_champion_check_interval_hours,
            )
        )

        return entries

    def start_scheduler(self) -> None:
        """Start the MLOps scheduler."""
        self.scheduler.start()

    def stop_scheduler(self) -> None:
        """Stop the MLOps scheduler."""
        self.scheduler.stop()

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset all component state (for testing)."""
        self.trainer.reset()
        self.evaluator.reset()
        self.deployer.reset()
        self.drift_detector.reset()
        self.champion_challenger.reset()
        self.rollback_manager.reset()
        self.lifecycle.reset()
        self.scheduler.reset()
        self.approval.reset()
        self._pipeline_runs.clear()
        self._pipeline_history.clear()
