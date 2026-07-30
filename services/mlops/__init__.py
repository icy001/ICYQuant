"""
ICYQuant MLOps & Continuous Training Platform.

Provides:
- Continuous Training (scheduled & event-driven retraining)
- Continuous Evaluation (post-training quality gates)
- Continuous Deployment (automated promotion to production)
- Data Drift Detection (PSI, KS, distribution shift)
- Model Drift Detection (prediction accuracy degradation)
- Champion / Challenger Framework
- Automatic Rollback (triggered by monitoring alerts)
- AI Lifecycle Management (full model lifecycle tracking)
- Approval Workflow (multi-stage review process)
"""

from services.mlops.trainer import (
    ContinuousTrainer, TrainingConfig, TrainingJob, TrainingTrigger,
    TrainingStatus, RetrainReason,
)
from services.mlops.evaluator import (
    ContinuousEvaluator, EvaluationConfig, EvaluationJob,
    EvaluationResult, EvaluationGate, GateStatus,
)
from services.mlops.deployment import (
    ContinuousDeployment, DeploymentConfig, DeploymentJob,
    DeploymentStrategy, DeploymentStatus,
)
from services.mlops.drift_detector import (
    DriftDetector, DriftConfig, DriftReport,
    DataDriftResult, ModelDriftResult, DriftSeverity,
    DriftMethod,
)
from services.mlops.champion_challenger import (
    ChampionChallenger, CCConfig, ChampionRecord,
    ChallengerRecord, CCResult, CCStatus, PromotionDecision,
)
from services.mlops.rollback import (
    RollbackManager, RollbackConfig, RollbackRule,
    RollbackEvent, RollbackStatus,
)
from services.mlops.lifecycle import (
    LifecycleManager, LifecycleConfig, LifecycleStage,
    LifecycleEvent, LifecycleRecord,
)
from services.mlops.scheduler import (
    MLOpsScheduler, SchedulerConfig, ScheduleEntry,
    ScheduleStatus, ScheduleTrigger,
)
from services.mlops.approval import (
    ApprovalManager, ApprovalConfig, ApprovalRequest,
    ApprovalStage, ApprovalStatus, ApprovalAction,
)
from services.mlops.service import (
    MLOpsService, MLOpsConfig, PipelineStatus, PipelineRun,
)

__all__ = [
    # Trainer
    "ContinuousTrainer", "TrainingConfig", "TrainingJob", "TrainingTrigger",
    "TrainingStatus", "RetrainReason",
    # Evaluator
    "ContinuousEvaluator", "EvaluationConfig", "EvaluationJob",
    "EvaluationResult", "EvaluationGate", "GateStatus",
    # Deployment
    "ContinuousDeployment", "DeploymentConfig", "DeploymentJob",
    "DeploymentStrategy", "DeploymentStatus",
    # Drift Detector
    "DriftDetector", "DriftConfig", "DriftReport",
    "DataDriftResult", "ModelDriftResult", "DriftSeverity",
    "DriftMethod",
    # Champion Challenger
    "ChampionChallenger", "CCConfig", "ChampionRecord",
    "ChallengerRecord", "CCResult", "CCStatus", "PromotionDecision",
    # Rollback
    "RollbackManager", "RollbackConfig", "RollbackRule",
    "RollbackEvent", "RollbackStatus",
    # Lifecycle
    "LifecycleManager", "LifecycleConfig", "LifecycleStage",
    "LifecycleEvent", "LifecycleRecord",
    # Scheduler
    "MLOpsScheduler", "SchedulerConfig", "ScheduleEntry",
    "ScheduleStatus", "ScheduleTrigger",
    # Approval
    "ApprovalManager", "ApprovalConfig", "ApprovalRequest",
    "ApprovalStage", "ApprovalStatus", "ApprovalAction",
    # Service
    "MLOpsService", "MLOpsConfig", "PipelineStatus", "PipelineRun",
]
