"""Feature Engineering Pipeline.

Automated feature generation, transformation, selection, and orchestration
for the ICYQuant AI platform.

Main components:
    - FeatureDAG: dependency graph for feature computation
    - FeatureTransformer: normalization, standardization, etc.
    - LabelGenerator: supervised learning label creation
    - FeatureSelector: variance, correlation, mutual information filters
    - FeatureImportance: post-training importance analysis
    - FeaturePipeline: single pipeline definition
    - PipelineOrchestrator: orchestration with retry/resume/checkpoint
    - PipelineScheduler: cron-style scheduling
    - FeatureCache: incremental computation cache
    - PipelineValidator: pipeline-level data validation
"""

from __future__ import annotations

from services.feature_engineering.dag import (
    DAGEdge,
    DAGNode,
    FeatureDAG,
    NodeState,
    dag_node,
)
from services.feature_engineering.transformer import (
    ClipTransformer,
    LogTransformer,
    NormalizeTransformer,
    RankTransformer,
    StandardizeTransformer,
    TransformContext,
    TransformResult,
    WinsorizeTransformer,
)
from services.feature_engineering.label_generator import (
    ClassificationLabelGenerator,
    LabelConfig,
    LabelType,
    RankingLabelGenerator,
    RegressionLabelGenerator,
)
from services.feature_engineering.selector import (
    CorrelationFilter,
    FeatureSelector,
    MutualInfoFilter,
    RFEliminator,
    SelectionReport,
    TreeImportanceFilter,
    VarianceFilter,
)
from services.feature_engineering.importance import (
    FeatureImportanceAnalyzer,
    ImportanceMethod,
    ImportanceReport,
)
from services.feature_engineering.pipeline import (
    FeaturePipeline,
    PipelineConfig,
    PipelineResult,
    PipelineStage,
    PipelineStatus,
)
from services.feature_engineering.orchestrator import (
    Checkpoint,
    OrchestratorConfig,
    PipelineOrchestrator,
    RetryPolicy,
    RunStatus,
)
from services.feature_engineering.scheduler import (
    PipelineScheduler,
    ScheduleConfig,
    ScheduleEntry,
    TriggerType,
)
from services.feature_engineering.cache import (
    CacheEntry,
    CachePolicy,
    FeatureCache,
)
from services.feature_engineering.validator import (
    PipelineValidationReport,
    PipelineValidator,
    PipelineValidationRule,
)

__all__ = [
    # DAG
    "FeatureDAG",
    "DAGNode",
    "DAGEdge",
    "NodeState",
    "dag_node",
    # Transformer
    "NormalizeTransformer",
    "StandardizeTransformer",
    "LogTransformer",
    "RankTransformer",
    "ClipTransformer",
    "WinsorizeTransformer",
    "TransformContext",
    "TransformResult",
    # Label
    "RegressionLabelGenerator",
    "ClassificationLabelGenerator",
    "RankingLabelGenerator",
    "LabelConfig",
    "LabelType",
    # Selector
    "FeatureSelector",
    "VarianceFilter",
    "CorrelationFilter",
    "MutualInfoFilter",
    "RFEliminator",
    "TreeImportanceFilter",
    "SelectionReport",
    # Importance
    "FeatureImportanceAnalyzer",
    "ImportanceMethod",
    "ImportanceReport",
    # Pipeline
    "FeaturePipeline",
    "PipelineConfig",
    "PipelineResult",
    "PipelineStage",
    "PipelineStatus",
    # Orchestrator
    "PipelineOrchestrator",
    "OrchestratorConfig",
    "Checkpoint",
    "RetryPolicy",
    "RunStatus",
    # Scheduler
    "PipelineScheduler",
    "ScheduleConfig",
    "ScheduleEntry",
    "TriggerType",
    # Cache
    "FeatureCache",
    "CacheEntry",
    "CachePolicy",
    # Validator
    "PipelineValidator",
    "PipelineValidationReport",
    "PipelineValidationRule",
]
