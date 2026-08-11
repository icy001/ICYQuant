"""ICYQuant service packages."""

import logging

logger = logging.getLogger(__name__)

# ── Core services (must succeed) ────────────────────────────────────────────

from services.common import EventBus, Settings, get_logger
from services.contracts import commands, dto, events, response
from services.eventbus import EventPublisher, EventSubscriber
from services.oms import Order, OrderManager, OrderStatus, OrderStateMachine
from services.position import PositionService


# ── Optional services (import failures are non-blocking) ─────────────────────

# Execution
try:
    from services.execution import ExecutionService, SimExecution
except ImportError:
    ExecutionService = None  # type: ignore
    SimExecution = None  # type: ignore

# Ledger
try:
    from services.ledger import LedgerDirection, LedgerEntry, LedgerService, LedgerType, PositionRebuilder, TradeToLedger
except ImportError:
    LedgerDirection = None; LedgerEntry = None; LedgerService = None; LedgerType = None; PositionRebuilder = None; TradeToLedger = None

# Risk
try:
    from services.risk import RiskEngine
except ImportError:
    RiskEngine = None  # type: ignore

# ML
try:
    from services.ml import MLService, MLConfig, ExperimentTracker, ModelRegistry, ArtifactManager, MetadataManager
except ImportError:
    MLService = None; MLConfig = None; ExperimentTracker = None; ModelRegistry = None; ArtifactManager = None; MetadataManager = None

# Feature Store
try:
    from services.feature_store import FeatureService, FeatureStoreConfig, FeatureRegistry, FeatureCatalog, FeatureLineage, FeatureVersioning, FeatureValidator, FeatureMonitor, OnlineFeatureStore, OfflineFeatureStore
except ImportError:
    FeatureService = None; FeatureStoreConfig = None; FeatureRegistry = None; FeatureCatalog = None; FeatureLineage = None
    FeatureVersioning = None; FeatureValidator = None; FeatureMonitor = None; OnlineFeatureStore = None; OfflineFeatureStore = None

# AutoML
try:
    from services.automl import (
        AutoMLService, SearchSpace, ParamType, CategoricalParam, ContinuousParam, DiscreteParam, ModelConfig,
        HyperOptimizer, SearchStrategy, OptimizationResult,
        TrialManager, TrialTask, TrialResult, TrialStatus,
        MultiObjectiveEvaluator, EvaluationResult, EvaluationMetric, ObjectiveConfig,
        AlphaDiscovery, AlphaCandidate, FactorTemplate, Operator,
        FactorCombiner, CombinedFactor, CombineMethod,
        WalkForwardValidator, WalkForwardConfig, WalkForwardResult, WindowResult,
        TimeSeriesCV, CVConfig, CVResult,
        Leaderboard, LeaderboardEntry, LeaderboardConfig, LeaderboardScope, RankMetric,
        PromotionManager, PromotionConfig, PromotionCriteria, PromotionResult, PromotionStage,
    )
except ImportError:
    pass

# Feature Engineering
try:
    from services.feature_engineering import (
        FeatureDAG, DAGNode, DAGEdge, NodeState, dag_node,
        NormalizeTransformer, StandardizeTransformer, LogTransformer, RankTransformer,
        ClipTransformer, WinsorizeTransformer, TransformContext, TransformResult,
        RegressionLabelGenerator, ClassificationLabelGenerator, RankingLabelGenerator,
        LabelConfig, LabelType,
        FeatureSelector, VarianceFilter, CorrelationFilter, MutualInfoFilter,
        RFEliminator, TreeImportanceFilter, SelectionReport,
        FeatureImportanceAnalyzer, ImportanceMethod, ImportanceReport,
        FeaturePipeline, PipelineConfig, PipelineResult, PipelineStage, PipelineStatus,
        PipelineOrchestrator, OrchestratorConfig, Checkpoint, RetryPolicy, RunStatus,
        PipelineScheduler, ScheduleConfig, ScheduleEntry, TriggerType,
        FeatureCache, CacheEntry, CachePolicy,
        PipelineValidator, PipelineValidationReport, PipelineValidationRule,
    )
except ImportError:
    pass

# Model Serving
try:
    from services.serving import (
        InferenceEngine, InferenceConfig, BatchInferenceRequest, BatchInferenceResult,
        OnlinePredictor, PredictResult, PredictRequest, PredictSignal, BatchPredictor,
        ModelLoader, LoadedModel, ModelFormat, LoadConfig,
        ModelRouter, RouteRule, RouteTarget, RouterConfig, RouteStrategy,
        FeatureJoiner, JoinResult, JoinSpec, JoinStrategy,
        PredictionCache, CachedPrediction, CacheConfig, CachePolicy,
        ABTesting, ABExperiment, ABVariant, ABResult, ABConfig, ABStatus,
        CanaryManager, CanaryStage, CanaryConfig, CanaryStatus, RolloutState,
        RolloutManager, RolloutConfig, RolloutPlan, RolloutStep, RolloutResult, RolloutStrategy,
        InferenceMonitor, MonitorConfig, LatencyMetric, QPSMetric, DriftMetric, HealthStatus,
        ServingService, ServingConfig, ServingMode,
    )
except ImportError:
    pass

# MLOps
try:
    from services.mlops import (
        ContinuousTrainer, TrainingConfig, TrainingJob, TrainingTrigger, TrainingStatus, RetrainReason,
        ContinuousEvaluator, EvaluationConfig, EvaluationJob, EvaluationResult, EvaluationGate, GateStatus,
        ContinuousDeployment, DeploymentConfig, DeploymentJob, DeploymentStrategy, DeploymentStatus,
        DriftDetector, DriftConfig, DriftReport, DataDriftResult, ModelDriftResult, DriftSeverity, DriftMethod,
        ChampionChallenger, CCConfig, ChampionRecord, ChallengerRecord, CCResult, CCStatus, PromotionDecision,
        RollbackManager, RollbackConfig, RollbackRule, RollbackEvent, RollbackStatus,
        LifecycleManager, LifecycleConfig, LifecycleStage, LifecycleEvent, LifecycleRecord,
        MLOpsScheduler, SchedulerConfig, ScheduleEntry, ScheduleStatus, ScheduleTrigger,
        ApprovalManager, ApprovalConfig, ApprovalRequest, ApprovalStage, ApprovalStatus, ApprovalAction,
        MLOpsService, MLOpsConfig, PipelineStatus, PipelineRun,
    )
except ImportError:
    pass

# Knowledge
try:
    from services.knowledge import (
        DataSource, RawDocument, DocumentType, IngestionConfig, IngestionPipeline,
        NewsEngine, NewsArticle, NewsConfig, NewsCategory, NewsSentiment,
        NLPProcessor, NLPResult, NLPTask, NLPTopic, NLPConfig,
        SentimentEngine, SentimentResult, SentimentDirection, SentimentConfig,
        SentimentMomentum, SentimentAcceleration, SentimentTrend,
        EntityExtractor, ExtractedEntity, EntityType, EntityMention, ExtractionConfig,
        EventEngine, MarketEvent, EventType as KnowledgeEventType, EventImpact, EventConfig, EventExtractionResult,
        KnowledgeGraph, GraphNode, GraphEdge, EdgeType, NodeType, GraphQuery,
        RelationEngine, EntityRelation, RelationType, RelationStrength, RelationConfig,
        EmbeddingEngine, DocumentEmbedding, EmbeddingConfig, EmbeddingModel, SimilarityResult, SearchQuery,
        EventAlphaEngine, AlphaSignal, SignalType, SignalConfidence, AlphaConfig, SignalPipeline, EventToSignalMapping,
        KnowledgeService, KnowledgeConfig, AnalysisRequest, AnalysisResult, PipelineResult, PipelineStatus as KnowledgePipelineStatus,
    )
except ImportError:
    pass

# Portfolio Management
try:
    from services.portfolio_management import (
        PortfolioManager, PortfolioConfig as PMPortfolioConfig, Portfolio as PMPortfolio, PortfolioGroup,
        AllocationTree, AllocationNode, AllocationType as PMAllocationType, PortfolioStatus as PMPortfolioStatus,
        CapitalAllocator, CapitalPool, AllocationRule, AllocationRequest, AllocationResult, AllocationMethod as PMAllocationMethod, CapitalFlow,
        StrategyAllocator, StrategyAllocation, StrategyType, StrategyRiskLevel, StrategyCapacity, StrategyConfig,
        RiskBudgetManager, RiskBudget, RiskBudgetType, RiskLimit, BudgetUtilization, RiskBucket,
        PortfolioOptimizer, OptimizationConfig, OptimizationObjective, OptimizationConstraint, OptimalPortfolio, OptimizationMethod,
        PortfolioRebalancer, RebalanceConfig, RebalanceMethod, RebalanceResult, TargetWeight, TradeList,
        PerformanceCalculator, PerformanceMetrics, ReturnSeries, RiskMetrics as PMRiskMetrics, PerformanceConfig as PMPerformanceConfig,
        AttributionEngine, AttributionResult, FactorAttribution, SectorAttribution, BrinsonAttribution, AttributionConfig as PMAttributionConfig,
        BenchmarkManager, Benchmark as PMBenchmark, BenchmarkType as PMBenchmarkType, BenchmarkFamily, TrackingError,
        AccountManager, TradingAccount, AccountType as PMAccountType,
        FundManager, FundOfFunds, SubFund, FoFAllocation, FoFPerformance, FoFRebalance,
        ReportingEngine, ReportTemplate, ReportType as PMReportType, PortfolioReport, ReportSection, ExportFormat,
    )
except ImportError:
    pass

# Data Platform
try:
    from services.data_platform import (
        DataPlatformService, DataPlatformConfig,
        DataLakehouse, DatasetSchema, DatasetType, WriteMode, DataFile, TableSnapshot,
        DataFabric, FabricQuery, FabricWriteRequest, FabricResult, FabricAccessPattern, DataView,
        MetadataCatalog, CatalogEntry, CatalogEntryType, ColumnMetadata, DatasetStatistics, SearchResult,
        SchemaRegistry, SchemaDefinition, FieldDefinition, FieldType, CompatibilityReport, ValidationResult,
        LineageTracker, LineageNode, LineageEdge, LineageChain, OperationType, ImpactAnalysis,
        QualityEngine, QualityRule, QualityReport, NotNullRule, UniqueRule, RangeRule, EnumRule, RegexRule, CustomRule, TimelinessRule,
        GovernanceEngine, DataOwner, RetentionPolicy, ComplianceReport, AuditEntry,
        AccessController, AccessDecision, UserAccess, Role, AccessRequest,
        VersionManager, VersionInfo, SnapshotDiff,
        TimeTravel, TimeTravelResult, TimeBranch, TimeTag,
        PartitionManager, PartitionInfo, PartitionSpec, CompactionResult,
        LifecycleManager, LifecyclePolicy, LifecycleReport, TierTransition, CostEstimate,
        DataPlatformAPI, APIResponse as DPAPIResponse,
        IngestRequest, QueryRequest, TimeTravelRequest, SnapshotRequest, SchemaRegisterRequest,
        StorageTier, DataClassification, QualityRuleType, AccessLevel, SchemaCompatibility, PartitionType,
        LifecycleAction, SnapshotFrequency,
    )
except ImportError:
    pass

# Reinforcement Learning
try:
    from services.reinforcement_learning import (
        RLTradingEnvironment, EnvironmentConfig, MarketState, EnvironmentStep, EnvironmentEpisode,
        TradingSimulator, SimulatorConfig, TradeResult, MarketImpactModel,
        RewardEngine, RewardConfig, RewardComponents, RewardType,
        StateEncoder, EncoderConfig, MarketEmbedding, EncodedState,
        ActionSpace, DiscreteActionSpace, ContinuousActionSpace, ActionType, ActionConfig,
        PolicyNetwork, PolicyConfig, ActorCriticNetwork, NetworkType,
        RLTrainer, TrainerConfig, TrainingResult, AlgorithmType, TrainingEpisode, TrainingMetrics,
        RLEvaluator, EvaluatorConfig, EvaluationResult, EvaluationMetrics,
        SelfPlayManager, SelfPlayConfig, SelfPlayAgent, CompetitionResult, AgentStrategy,
        RegimeAdapter, RegimeConfig, MarketRegime, RegimePolicy,
        RLPortfolioOptimizer, OptimizerConfig as RLOptimizerConfig, PortfolioAllocation, AllocationResult as RLAllocationResult,
        RLService, RLServiceConfig, RLServiceStatus, TrainingJob,
        RLAPI, APIResponse,
    )
except ImportError:
    pass


__all__ = [
    "EventBus",
    "EventPublisher",
    "EventSubscriber",
    "ExecutionService",
    "SimExecution",
    "LedgerDirection",
    "LedgerEntry",
    "LedgerService",
    "LedgerType",
    "Order",
    "OrderManager",
    "OrderStatus",
    "OrderStateMachine",
    "PositionRebuilder",
    "PositionService",
    "RiskEngine",
    "Settings",
    "TradeToLedger",
    "commands",
    "dto",
    "events",
    "get_logger",
    "response",
    "MLService",
    "MLConfig",
    "ExperimentTracker",
    "ModelRegistry",
    "ArtifactManager",
    "MetadataManager",
    "FeatureService",
    "FeatureStoreConfig",
    "FeatureRegistry",
    "FeatureCatalog",
    "FeatureLineage",
    "FeatureVersioning",
    "FeatureValidator",
    "FeatureMonitor",
    "OnlineFeatureStore",
    "OfflineFeatureStore",
    # AutoML
    "AutoMLService",
    "SearchSpace", "ParamType", "CategoricalParam", "ContinuousParam", "DiscreteParam", "ModelConfig",
    "HyperOptimizer", "SearchStrategy", "OptimizationResult",
    "TrialManager", "TrialTask", "TrialResult", "TrialStatus",
    "MultiObjectiveEvaluator", "EvaluationResult", "EvaluationMetric", "ObjectiveConfig",
    "AlphaDiscovery", "AlphaCandidate", "FactorTemplate", "Operator",
    "FactorCombiner", "CombinedFactor", "CombineMethod",
    "WalkForwardValidator", "WalkForwardConfig", "WalkForwardResult", "WindowResult",
    "TimeSeriesCV", "CVConfig", "CVResult",
    "Leaderboard", "LeaderboardEntry", "LeaderboardConfig", "LeaderboardScope", "RankMetric",
    "PromotionManager", "PromotionConfig", "PromotionCriteria", "PromotionResult", "PromotionStage",
    # Feature Engineering
    "FeatureDAG", "DAGNode", "DAGEdge", "NodeState", "dag_node",
    "NormalizeTransformer", "StandardizeTransformer", "LogTransformer", "RankTransformer",
    "ClipTransformer", "WinsorizeTransformer", "TransformContext", "TransformResult",
    "RegressionLabelGenerator", "ClassificationLabelGenerator", "RankingLabelGenerator",
    "LabelConfig", "LabelType",
    "FeatureSelector", "VarianceFilter", "CorrelationFilter", "MutualInfoFilter",
    "RFEliminator", "TreeImportanceFilter", "SelectionReport",
    "FeatureImportanceAnalyzer", "ImportanceMethod", "ImportanceReport",
    "FeaturePipeline", "PipelineConfig", "PipelineResult", "PipelineStage", "PipelineStatus",
    "PipelineOrchestrator", "OrchestratorConfig", "Checkpoint", "RetryPolicy", "RunStatus",
    "PipelineScheduler", "ScheduleConfig", "ScheduleEntry", "TriggerType",
    "FeatureCache", "CacheEntry", "CachePolicy",
    "PipelineValidator", "PipelineValidationReport", "PipelineValidationRule",
    # Model Serving
    "InferenceEngine", "InferenceConfig", "BatchInferenceRequest", "BatchInferenceResult",
    "OnlinePredictor", "PredictResult", "PredictRequest", "PredictSignal", "BatchPredictor",
    "ModelLoader", "LoadedModel", "ModelFormat", "LoadConfig",
    "ModelRouter", "RouteRule", "RouteTarget", "RouterConfig", "RouteStrategy",
    "FeatureJoiner", "JoinResult", "JoinSpec", "JoinStrategy",
    "PredictionCache", "CachedPrediction", "CacheConfig", "CachePolicy",
    "ABTesting", "ABExperiment", "ABVariant", "ABResult", "ABConfig", "ABStatus",
    "CanaryManager", "CanaryStage", "CanaryConfig", "CanaryStatus", "RolloutState",
    "RolloutManager", "RolloutConfig", "RolloutPlan", "RolloutStep", "RolloutResult", "RolloutStrategy",
    "InferenceMonitor", "MonitorConfig", "LatencyMetric", "QPSMetric", "DriftMetric", "HealthStatus",
    "ServingService", "ServingConfig", "ServingMode",
    # MLOps
    "ContinuousTrainer", "TrainingConfig", "TrainingJob", "TrainingTrigger", "TrainingStatus", "RetrainReason",
    "ContinuousEvaluator", "EvaluationConfig", "EvaluationJob", "EvaluationResult", "EvaluationGate", "GateStatus",
    "ContinuousDeployment", "DeploymentConfig", "DeploymentJob", "DeploymentStrategy", "DeploymentStatus",
    "DriftDetector", "DriftConfig", "DriftReport", "DataDriftResult", "ModelDriftResult", "DriftSeverity", "DriftMethod",
    "ChampionChallenger", "CCConfig", "ChampionRecord", "ChallengerRecord", "CCResult", "CCStatus", "PromotionDecision",
    "RollbackManager", "RollbackConfig", "RollbackRule", "RollbackEvent", "RollbackStatus",
    "LifecycleManager", "LifecycleConfig", "LifecycleStage", "LifecycleEvent", "LifecycleRecord",
    "MLOpsScheduler", "SchedulerConfig", "ScheduleEntry", "ScheduleStatus", "ScheduleTrigger",
    "ApprovalManager", "ApprovalConfig", "ApprovalRequest", "ApprovalStage", "ApprovalStatus", "ApprovalAction",
    "MLOpsService", "MLOpsConfig", "PipelineStatus", "PipelineRun",
    # Knowledge
    "DataSource", "RawDocument", "DocumentType", "IngestionConfig", "IngestionPipeline",
    "NewsEngine", "NewsArticle", "NewsConfig", "NewsCategory", "NewsSentiment",
    "NLPProcessor", "NLPResult", "NLPTask", "NLPTopic", "NLPConfig",
    "SentimentEngine", "SentimentResult", "SentimentDirection", "SentimentConfig",
    "SentimentMomentum", "SentimentAcceleration", "SentimentTrend",
    "EntityExtractor", "ExtractedEntity", "EntityType", "EntityMention", "ExtractionConfig",
    "EventEngine", "MarketEvent", "KnowledgeEventType", "EventImpact", "EventConfig", "EventExtractionResult",
    "KnowledgeGraph", "GraphNode", "GraphEdge", "EdgeType", "NodeType", "GraphQuery",
    "RelationEngine", "EntityRelation", "RelationType", "RelationStrength", "RelationConfig",
    "EmbeddingEngine", "DocumentEmbedding", "EmbeddingConfig", "EmbeddingModel", "SimilarityResult", "SearchQuery",
    "EventAlphaEngine", "AlphaSignal", "SignalType", "SignalConfidence", "AlphaConfig", "SignalPipeline", "EventToSignalMapping",
    "KnowledgeService", "KnowledgeConfig", "AnalysisRequest", "AnalysisResult", "PipelineResult", "KnowledgePipelineStatus",
    # Portfolio Management
    "PortfolioManager", "PMPortfolioConfig", "PMPortfolio", "PortfolioGroup",
    "AllocationTree", "AllocationNode", "PMAllocationType", "PMPortfolioStatus",
    "CapitalAllocator", "CapitalPool", "AllocationRule", "AllocationRequest", "AllocationResult", "PMAllocationMethod", "CapitalFlow",
    "StrategyAllocator", "StrategyAllocation", "StrategyType", "StrategyRiskLevel", "StrategyCapacity", "StrategyConfig",
    "RiskBudgetManager", "RiskBudget", "RiskBudgetType", "RiskLimit", "BudgetUtilization", "RiskBucket",
    "PortfolioOptimizer", "OptimizationConfig", "OptimizationObjective", "OptimizationConstraint", "OptimalPortfolio", "OptimizationMethod",
    "PortfolioRebalancer", "RebalanceConfig", "RebalanceMethod", "RebalanceResult", "TargetWeight", "TradeList",
    "PerformanceCalculator", "PerformanceMetrics", "ReturnSeries", "PMRiskMetrics", "PMPerformanceConfig",
    "AttributionEngine", "AttributionResult", "FactorAttribution", "SectorAttribution", "BrinsonAttribution", "PMAttributionConfig",
    "BenchmarkManager", "PMBenchmark", "PMBenchmarkType", "BenchmarkFamily", "TrackingError",
    "AccountManager", "TradingAccount", "PMAccountType",
    "FundManager", "FundOfFunds", "SubFund", "FoFAllocation", "FoFPerformance", "FoFRebalance",
    "ReportingEngine", "ReportTemplate", "PMReportType", "PortfolioReport", "ReportSection", "ExportFormat",
    # Data Platform
    "DataPlatformService", "DataPlatformConfig",
    "DataLakehouse", "DatasetSchema", "DatasetType", "WriteMode", "DataFile", "TableSnapshot",
    "DataFabric", "FabricQuery", "FabricWriteRequest", "FabricResult", "FabricAccessPattern", "DataView",
    "MetadataCatalog", "CatalogEntry", "CatalogEntryType", "ColumnMetadata", "DatasetStatistics", "SearchResult",
    "SchemaRegistry", "SchemaDefinition", "FieldDefinition", "FieldType", "CompatibilityReport", "ValidationResult",
    "LineageTracker", "LineageNode", "LineageEdge", "LineageChain", "OperationType", "ImpactAnalysis",
    "QualityEngine", "QualityRule", "QualityReport", "NotNullRule", "UniqueRule", "RangeRule", "EnumRule", "RegexRule", "CustomRule", "TimelinessRule",
    "GovernanceEngine", "DataOwner", "RetentionPolicy", "ComplianceReport", "AuditEntry",
    "AccessController", "AccessDecision", "UserAccess", "Role", "AccessRequest",
    "VersionManager", "VersionInfo", "SnapshotDiff",
    "TimeTravel", "TimeTravelResult", "TimeBranch", "TimeTag",
    "PartitionManager", "PartitionInfo", "PartitionSpec", "CompactionResult",
    "LifecycleManager", "LifecyclePolicy", "LifecycleReport", "TierTransition", "CostEstimate",
    "DataPlatformAPI", "DPAPIResponse",
    "IngestRequest", "QueryRequest", "TimeTravelRequest", "SnapshotRequest", "SchemaRegisterRequest",
    "StorageTier", "DataClassification", "QualityRuleType", "AccessLevel", "SchemaCompatibility", "PartitionType",
    "LifecycleAction", "SnapshotFrequency",
    # Reinforcement Learning
    "RLTradingEnvironment", "EnvironmentConfig", "MarketState", "EnvironmentStep", "EnvironmentEpisode",
    "TradingSimulator", "SimulatorConfig", "TradeResult", "MarketImpactModel",
    "RewardEngine", "RewardConfig", "RewardComponents", "RewardType",
    "StateEncoder", "EncoderConfig", "MarketEmbedding", "EncodedState",
    "ActionSpace", "DiscreteActionSpace", "ContinuousActionSpace", "ActionType", "ActionConfig",
    "PolicyNetwork", "PolicyConfig", "ActorCriticNetwork", "NetworkType",
    "RLTrainer", "TrainerConfig", "TrainingResult", "AlgorithmType", "TrainingEpisode", "TrainingMetrics",
    "RLEvaluator", "EvaluatorConfig", "EvaluationResult", "EvaluationMetrics",
    "SelfPlayManager", "SelfPlayConfig", "SelfPlayAgent", "CompetitionResult", "AgentStrategy",
    "RegimeAdapter", "RegimeConfig", "MarketRegime", "RegimePolicy",
    "RLPortfolioOptimizer", "RLOptimizerConfig", "PortfolioAllocation", "RLAllocationResult",
    "RLService", "RLServiceConfig", "RLServiceStatus", "TrainingJob",
    "RLAPI", "APIResponse",
]
