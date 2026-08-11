"""
ICYQuant ML Platform - Enterprise Feature Store & Machine Learning Pipeline.

Commit 17 Part 1.3: Feature Store, Training Dataset Builder, ML Pipeline,
Model Registry, Experiment Tracking, Drift Detection, Reproducibility.

Architecture:
    Market Data → Feature Store (Offline + Online) → Training Dataset
    → ML Training → Model Registry → Prediction → Strategy

Key components:
    - Feature Store: Unified feature registration, offline/online serving
    - Feature Pipeline: Normalization → Transformation → Validation → Storage
    - Training Dataset: Point-in-time correct, fully reproducible
    - ML Training: Multi-framework, hyperparameter search, cross-validation
    - Model Registry: Full lifecycle (training → production → archived)
    - Drift Detection: Data, feature, and prediction drift monitoring
    - Reproducibility: Complete context capture for every artifact
"""

from __future__ import annotations

# Core Platform
from .ml_platform import MLPlatform, MLPlatformConfig, PlatformState, PlatformStatus, get_platform
from .ml_runtime import MLRuntime, MLJob, RunContext, JobType, JobPriority, RuntimeState
from .ml_manager import MLManager, ManagerStatus, SubsystemState, SubsystemInfo
from .ml_orchestrator import MLOrchestrator, OrchContext, OrchPhase, OrchestrationPhase, PhaseResult

# Feature Store
from .feature_store import FeatureStore, FeatureStoreConfig
from .feature_registry import FeatureRegistry, FeatureEntry, FeatureCategory, FeatureFrequency, NullPolicy, OutlierPolicy
from .feature_definition import FeatureDefinition
from .feature_group import FeatureGroup, FeatureGroupManager
from .feature_view import FeatureView, FeatureViewConfig, FeatureViewManager

# Feature Pipeline
from .feature_pipeline import FeaturePipeline, PipelineRun, PipelineStage, PipelineStatus
from .feature_engine import FeatureEngine, ComputeRequest, ComputeResult
from .feature_transformer import FeatureTransformer, TransformType, TransformSpec, TransformPipeline
from .feature_validator import FeatureValidator, ValidationReport, ValidationIssue, ValidationSeverity
from .feature_quality import FeatureQualityEngine, QualityReport, QualityDimension, QualityLevel

# Feature Management
from .feature_lineage import FeatureLineage, LineageGraph, LineageNode, LineageEdge, LineageNodeType
from .feature_version import FeatureVersion, FeatureVersionManager, VersionStatus
from .feature_snapshot import FeatureSnapshot, SnapshotManager
from .feature_cache import FeatureCache, CacheEntry, CacheStats

# Stores
from .offline_store import OfflineFeatureStore, OfflineStoreConfig, QueryResult
from .online_store import OnlineFeatureStore, OnlineStoreConfig, OnlineQueryResult

# Training Dataset
from .training_dataset import TrainingDataset, DatasetMetadata
from .dataset_builder import DatasetBuilder, DatasetBuildConfig, BuildReport
from .label_engine import LabelEngine, LabelConfig, LabelType, LabelHorizon, LabelResult
from .sample_generator import SampleGenerator, SamplingConfig, SamplingMethod, SampleWeightMethod

# Training
from .train_test_split import TrainTestSplitter, SplitConfig, SplitResult, SplitMethod
from .model_training import ModelTrainer, TrainingConfig, TrainingRun, Framework, TrainingStatus
from .model_evaluator import ModelEvaluator, EvaluationReport, EvaluationMetrics, EvaluationType
from .hyperparameter_search import HyperparameterSearch, SearchConfig, SearchResult, ParamSpace, SearchMethod
from .cross_validator import CrossValidator, CVConfig, CVResult, CVFold, CVMethod

# Experiment & Model Registry
from .experiment_manager import ExperimentManager, ExperimentConfig, ExperimentRun, ExperimentStatus
from .experiment_tracker import ExperimentTracker, ExperimentRecord
from .model_registry import ModelRegistry, ModelEntry, ModelStatus
from .model_version import ModelVersion, ModelVersionManager, VersionStage
from .model_artifact import ModelArtifact, ModelArtifactManager, ArtifactFormat, ArtifactBackend
from .model_metadata import ModelMetadata, ModelCategory, ModelRiskTier

# Pipeline Management
from .pipeline_scheduler import PipelineScheduler, ScheduleConfig, ScheduleType
from .pipeline_state import PipelineStateManager, PipelineState, PipelineRunStatus
from .pipeline_checkpoint import PipelineCheckpointManager, CheckpointData
from .lineage_tracker import LineageTracker, LineageRecord, ArtifactType, RelationType

# Drift Detection
from .drift_detector import DriftDetector, DriftReport, DriftSeverity, DriftConfig
from .data_drift import DataDriftDetector, DataDriftResult, DriftMethod
from .feature_drift import FeatureDriftDetector, FeatureDriftResult, FeatureDriftSummary
from .prediction_drift import PredictionDriftDetector, PredictionDriftResult

# Reproducibility
from .reproducibility import ReproducibilityManager, ReproducibilityManifest, ReproducibilityCheck

# Observability
from .metrics import (
    MLMetricsCollector, get_metrics,
    record_feature_computed, record_dataset_created,
    record_experiment_run, record_training_run,
    record_model_version, record_model_evaluation,
    record_feature_drift, record_prediction_drift,
    record_feature_quality,
)
from .telemetry import (
    TelemetryTracer, TelemetrySpan, SpanEvent, SpanKind,
)
from .diagnostics import MLDiagnostics, DiagnosticsReport, DiagnosticResult, DiagnosticLevel
from .health import MLHealthChecker, HealthReport, HealthCheckResult, HealthStatus


__all__ = [
    # Core
    "MLPlatform", "MLPlatformConfig", "PlatformState", "PlatformStatus", "get_platform",
    "MLRuntime", "MLJob", "RunContext", "JobType", "JobPriority",
    "MLManager", "ManagerStatus",
    "MLOrchestrator", "OrchContext", "PhaseResult",

    # Feature Store
    "FeatureStore", "FeatureStoreConfig",
    "FeatureRegistry", "FeatureEntry", "FeatureCategory", "FeatureFrequency",
    "FeatureDefinition",
    "FeatureGroup", "FeatureGroupManager",
    "FeatureView", "FeatureViewConfig", "FeatureViewManager",

    # Feature Pipeline
    "FeaturePipeline", "PipelineStage", "PipelineStatus",
    "FeatureEngine", "ComputeRequest", "ComputeResult",
    "FeatureTransformer", "TransformType", "TransformSpec",
    "FeatureValidator", "ValidationReport",
    "FeatureQualityEngine", "QualityReport", "QualityLevel",

    # Feature Management
    "FeatureLineage", "LineageNodeType",
    "FeatureVersion", "FeatureVersionManager",
    "FeatureSnapshot", "SnapshotManager",
    "FeatureCache", "CacheStats",

    # Stores
    "OfflineFeatureStore", "OnlineFeatureStore",

    # Training Dataset
    "TrainingDataset", "DatasetMetadata",
    "DatasetBuilder", "DatasetBuildConfig",
    "LabelEngine", "LabelType", "LabelHorizon",
    "SampleGenerator", "SamplingMethod",

    # Training
    "TrainTestSplitter", "SplitMethod",
    "ModelTrainer", "Framework", "TrainingStatus",
    "ModelEvaluator", "EvaluationMetrics",
    "HyperparameterSearch", "SearchMethod",
    "CrossValidator", "CVMethod",

    # Experiment & Model
    "ExperimentManager", "ExperimentStatus",
    "ExperimentTracker", "ExperimentRecord",
    "ModelRegistry", "ModelEntry", "ModelStatus",
    "ModelVersion", "ModelVersionManager",
    "ModelArtifact", "ModelArtifactManager",
    "ModelMetadata", "ModelCategory", "ModelRiskTier",

    # Pipeline
    "PipelineScheduler", "ScheduleType",
    "PipelineStateManager", "PipelineState",
    "PipelineCheckpointManager", "CheckpointData",
    "LineageTracker", "ArtifactType", "RelationType",

    # Drift
    "DriftDetector", "DriftReport", "DriftSeverity",
    "DataDriftDetector", "FeatureDriftDetector", "PredictionDriftDetector",

    # Reproducibility
    "ReproducibilityManager", "ReproducibilityManifest",

    # Observability
    "MLMetricsCollector", "get_metrics",
    "TelemetryTracer", "TelemetrySpan", "SpanKind",
    "MLDiagnostics", "DiagnosticsReport",
    "MLHealthChecker", "HealthReport", "HealthStatus",
]

__version__ = "0.4.0-alpha2"
