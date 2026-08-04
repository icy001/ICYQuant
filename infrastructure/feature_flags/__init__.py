"""
Feature Flag Platform.

Provides a comprehensive feature flag system for
controlling feature rollout, A/B testing, kill
switches, and percentage-based deployments.

Architecture:
    Application
          ↓
    FeatureFlagService
          ↓
    FeatureFlagManager
          ↓
    FeatureRegistry → FeatureEvaluator → FeatureFlagCache
          ↓
    FeatureStorage (memory/YAML/database/redis/remote)

Usage:
    from infrastructure.feature_flags import (
        FeatureFlagService,
        FeatureFlagManager,
        FeatureFlagConfig,
        FeatureFlag,
        FeatureContext,
    )

    service = FeatureFlagService(FeatureFlagConfig())
    await service.start()
    enabled = await service.is_enabled("my.feature")
"""

# Configuration
from .config import FeatureFlagConfig

# Constants
from .constants import (
    DEFAULT_CACHE_MAX_SIZE,
    DEFAULT_CACHE_TTL,
    DEFAULT_EVAL_TIMEOUT_SECONDS,
    DEFAULT_MAX_RULES_PER_FLAG,
    DEFAULT_STORAGE_BACKEND,
    EvaluationResult,
    EvaluationStrategy,
    FeatureFlagType,
    FlagStatus,
    OperatorAction,
    StorageBackend,
)

# Models
from .models import (
    AuditEntry,
    FeatureContext,
    FeatureEvaluationResult,
    FeatureFlag,
    FeatureFlagCacheEntry,
    FeatureRule,
)

# Exceptions
from .exceptions import (
    CanaryDeploymentError,
    CanaryError,
    CanaryHealthError,
    CanaryPromotionError,
    CanaryRollbackError,
    ExperimentAllocationError,
    ExperimentAnalysisError,
    ExperimentError,
    ExperimentNotFoundError,
    ExperimentValidationError,
    FeatureFlagAlreadyExistsError,
    FeatureFlagCacheError,
    FeatureFlagCircuitError,
    FeatureFlagError,
    FeatureFlagEvaluationError,
    FeatureFlagNotFoundError,
    FeatureFlagStorageError,
    FeatureFlagValidationError,
    TargetingRuleCompileError,
    TargetingRuleError,
    TargetingRuleEvalError,
    TargetingRuleParseError,
)

# Storage
from .storage import (
    DatabaseFeatureStorage,
    FeatureStorage,
    MemoryFeatureStorage,
    RedisFeatureStorage,
    RemoteFeatureStorage,
    YAMLFeatureStorage,
    create_storage,
)

# Cache
from .cache import FeatureFlagCache

# Registry
from .registry import FeatureRegistry

# Evaluator
from .evaluator import FeatureEvaluator

# Manager
from .manager import FeatureFlagManager

# Resolver
from .resolver import CachedResolver, FeatureResolver

# Audit
from .audit import AuditManager

# Metrics
from .metrics import (
    METRIC_AUDIT_TOTAL,
    METRIC_CACHE_HIT_TOTAL,
    METRIC_CACHE_MISS_TOTAL,
    METRIC_CIRCUIT_BREAKER_TOTAL,
    METRIC_DELETED_TOTAL,
    METRIC_DISABLED_TOTAL,
    METRIC_ENABLED_TOTAL,
    METRIC_ERROR_TOTAL,
    METRIC_EVAL_DURATION,
    METRIC_EVAL_TOTAL,
    METRIC_REGISTERED_TOTAL,
    METRIC_UPDATED_TOTAL,
    FeatureFlagMetrics,
    FeatureFlagPrometheusExporter,
)

# Health
from .health import (
    HealthCheckResult,
    FeatureFlagHealth,
)

# Validator
from .validator import FeatureFlagValidator

# Service
from .service import FeatureFlagService

# Targeting Rules
from .targeting import (
    AndNode,
    CompiledRuleCache,
    ConditionNode,
    EvaluationCache,
    LogicNode,
    MatcherFn,
    NotNode,
    OPERATOR_ORDER,
    OPERATOR_SYMBOLS,
    OrNode,
    ParseError,
    PriorityLevel,
    PriorityResult,
    PriorityResolver,
    RuleEvaluation,
    RuleMetrics,
    RuleNode,
    RuleParser,
    RuleCompiler,
    RuleMatcher,
    RuleSet,
    RuleValidator,
    Operator,
    TargetContext,
    TargetRule,
    TargetingEngine,
    compare_eq,
    compare_neq,
    compare_gt,
    compare_gte,
    compare_lt,
    compare_lte,
    compare_in,
    compare_not_in,
    compare_starts_with,
    compare_ends_with,
    compare_contains,
    compare_regex,
    flatten_conditions,
    get_compare_fn,
    node_count,
    node_depth,
    parse_expression,
)

# Rollout
from .rollout import (
    RolloutEngine,
    RolloutPolicy,
    RolloutAssignment,
    ConsistentHasher,
    compute_hash,
    is_in_percentage_rollout,
    StickyAssignment,
    ProgressiveRollout,
    ProgressiveStage,
    SegmentDefinition,
    SegmentEngine,
    RolloutStrategy,
    RolloutScheduler,
    ScheduleConfig,
    RolloutValidator,
    RolloutMetrics,
    RolloutAudit,
    RolloutCache,
    FREQUENCY_IMMEDIATE,
    FREQUENCY_DAILY,
    FREQUENCY_WEEKLY,
)

# Diagnostics
from .diagnostics import (
    EvaluationTrace,
    RuleDiagnostics,
    TraceStep,
)

# Canary
from .canary import (
    AGGRESSIVE_POLICY,
    BALANCED_POLICY,
    CONSERVATIVE_POLICY,
    CanaryAudit,
    CanaryDeployment,
    CanaryDeploymentManager,
    CanaryManager,
    CanaryMetrics,
    CanaryMonitor,
    CanaryPolicy,
    CanaryStage,
    CanaryValidator,
    DEFAULT_CANARY_STAGES,
    HealthCheckResult as CanaryHealthCheckResult,
    HealthMonitor,
    HealthStatus,
    MonitorSnapshot,
    PromotionDecision,
    PromotionEngine,
    RollbackManager,
)

# Experiments
from .experiments import (
    AnalysisResult,
    Experiment,
    ExperimentAnalyzer,
    ExperimentArchive,
    ExperimentAudit,
    ExperimentManager,
    ExperimentMetrics,
    ExperimentResult,
    ExperimentStatus,
    ExperimentValidator,
    StatisticsCollector,
    Variant,
    VariantAllocator,
    VariantStats,
    WinnerResult,
    WinnerSelector,
    create_ab_variants,
    create_abc_variants,
)

# Utils
from .utils import (
    clamp,
    compact_dict,
    compute_checksum,
    consistent_hash,
    deep_merge,
    format_timestamp,
    generate_id,
    generate_trace_id,
    is_in_rollout,
    parse_timestamp,
    sanitize_flag_key,
    serialize_flag,
)

# Snapshot
from .snapshot import (
    FeatureSnapshot,
    SnapshotManager,
)

# Version
from .version import (
    VersionEntry,
    VersionManager,
)

# Events
from .events import (
    EventBus,
    FeatureEvent,
    FeatureEventType,
)

# Publisher
from .publisher import FeatureEventPublisher

# Subscriber
from .subscriber import (
    FeatureEventSubscriber,
    SubscriberType,
)

# Runtime
from .runtime import RuntimeFeatureService

# Hot Reload
from .hotreload import HotReloadManager

# Protection
from .protection import (
    CircuitBreaker,
    EvaluationRateLimiter,
    PlatformProtection,
    SnapshotIntegrityChecker,
)

# Recovery
from .recovery import RecoveryManager

# Monitoring
from .monitoring import FeatureFlagRuntimeMetrics

# Telemetry
from .telemetry import FeatureFlagTelemetry

# Container
from .container import ServiceContainer

# Lifecycle
from .lifecycle import (
    LifecycleState,
    PlatformLifecycle,
)

# Scheduler
from .scheduler import FeatureFlagScheduler

# Synchronization
from .synchronization import SynchronizationManager

# Integration
from .integration import PlatformIntegration

# Bootstrap
from .bootstrap import FeatureFlagBootstrap

__all__ = [
    # Config
    "FeatureFlagConfig",
    # Constants
    "DEFAULT_CACHE_MAX_SIZE",
    "DEFAULT_CACHE_TTL",
    "DEFAULT_EVAL_TIMEOUT_SECONDS",
    "DEFAULT_MAX_RULES_PER_FLAG",
    "DEFAULT_STORAGE_BACKEND",
    "EvaluationResult",
    "EvaluationStrategy",
    "FeatureFlagType",
    "FlagStatus",
    "OperatorAction",
    "StorageBackend",
    # Models
    "AuditEntry",
    "FeatureContext",
    "FeatureEvaluationResult",
    "FeatureFlag",
    "FeatureFlagCacheEntry",
    "FeatureRule",
    # Exceptions
    "CanaryDeploymentError",
    "CanaryError",
    "CanaryHealthError",
    "CanaryPromotionError",
    "CanaryRollbackError",
    "ExperimentAllocationError",
    "ExperimentAnalysisError",
    "ExperimentError",
    "ExperimentNotFoundError",
    "ExperimentValidationError",
    "FeatureFlagAlreadyExistsError",
    "FeatureFlagCacheError",
    "FeatureFlagCircuitError",
    "FeatureFlagError",
    "FeatureFlagEvaluationError",
    "FeatureFlagNotFoundError",
    "FeatureFlagStorageError",
    "FeatureFlagValidationError",
    "TargetingRuleCompileError",
    "TargetingRuleError",
    "TargetingRuleEvalError",
    "TargetingRuleParseError",
    # Storage
    "DatabaseFeatureStorage",
    "FeatureStorage",
    "MemoryFeatureStorage",
    "RedisFeatureStorage",
    "RemoteFeatureStorage",
    "YAMLFeatureStorage",
    "create_storage",
    # Cache
    "FeatureFlagCache",
    # Registry
    "FeatureRegistry",
    # Evaluator
    "FeatureEvaluator",
    # Manager
    "FeatureFlagManager",
    # Resolver
    "CachedResolver",
    "FeatureResolver",
    # Audit
    "AuditManager",
    # Metrics
    "METRIC_AUDIT_TOTAL",
    "METRIC_CACHE_HIT_TOTAL",
    "METRIC_CACHE_MISS_TOTAL",
    "METRIC_CIRCUIT_BREAKER_TOTAL",
    "METRIC_DELETED_TOTAL",
    "METRIC_DISABLED_TOTAL",
    "METRIC_ENABLED_TOTAL",
    "METRIC_ERROR_TOTAL",
    "METRIC_EVAL_DURATION",
    "METRIC_EVAL_TOTAL",
    "METRIC_REGISTERED_TOTAL",
    "METRIC_UPDATED_TOTAL",
    "METRIC_RULE_TOTAL",
    "METRIC_RULE_MATCH_TOTAL",
    "METRIC_RULE_CACHE_HIT_TOTAL",
    "METRIC_RULE_COMPILE_TOTAL",
    "METRIC_RULE_EVAL_SECONDS",
    "FeatureFlagMetrics",
    "FeatureFlagPrometheusExporter",
    # Health
    "HealthCheckResult",
    "FeatureFlagHealth",
    # Validator
    "FeatureFlagValidator",
    # Service
    "FeatureFlagService",
    # Targeting Rules
    "TargetingEngine",
    "RuleMatcher",
    "RuleCompiler",
    "OptimizedRuleCompiler",
    "RuleParser",
    "RuleValidator",
    "PriorityResolver",
    "TargetContext",
    "TargetRule",
    "RuleSet",
    "RuleEvaluation",
    "RuleNode",
    "LogicNode",
    "ConditionNode",
    "AndNode",
    "OrNode",
    "NotNode",
    "Operator",
    "OPERATOR_ORDER",
    "OPERATOR_SYMBOLS",
    "compare_eq",
    "compare_neq",
    "compare_gt",
    "compare_gte",
    "compare_lt",
    "compare_lte",
    "compare_in",
    "compare_not_in",
    "compare_starts_with",
    "compare_ends_with",
    "compare_contains",
    "compare_regex",
    "get_compare_fn",
    "CompiledRuleCache",
    "EvaluationCache",
    "RuleMetrics",
    "PriorityLevel",
    "PriorityResult",
    "MatcherFn",
    "ParseError",
    "parse_expression",
    "flatten_conditions",
    "node_count",
    "node_depth",
    # Diagnostics
    "EvaluationTrace",
    "RuleDiagnostics",
    "TraceStep",
    # Canary
    "CanaryManager",
    "CanaryDeployment",
    "CanaryDeploymentManager",
    "CanaryStage",
    "CanaryPolicy",
    "CanaryValidator",
    "CanaryMetrics",
    "CanaryAudit",
    "CanaryMonitor",
    "CanaryHealthCheckResult",
    "HealthMonitor",
    "HealthStatus",
    "MonitorSnapshot",
    "RollbackManager",
    "PromotionEngine",
    "PromotionDecision",
    "DEFAULT_CANARY_STAGES",
    "CONSERVATIVE_POLICY",
    "BALANCED_POLICY",
    "AGGRESSIVE_POLICY",
    # Experiments
    "ExperimentManager",
    "Experiment",
    "ExperimentResult",
    "ExperimentStatus",
    "Variant",
    "VariantAllocator",
    "VariantStats",
    "StatisticsCollector",
    "ExperimentAnalyzer",
    "AnalysisResult",
    "WinnerSelector",
    "WinnerResult",
    "ExperimentArchive",
    "ExperimentValidator",
    "ExperimentMetrics",
    "ExperimentAudit",
    "create_ab_variants",
    "create_abc_variants",
    # Rollout
    "RolloutEngine",
    "RolloutPolicy",
    "RolloutAssignment",
    "ConsistentHasher",
    "compute_hash",
    "is_in_percentage_rollout",
    "StickyAssignment",
    "ProgressiveRollout",
    "ProgressiveStage",
    "SegmentDefinition",
    "SegmentEngine",
    "RolloutStrategy",
    "RolloutScheduler",
    "ScheduleConfig",
    "RolloutValidator",
    "RolloutMetrics",
    "RolloutAudit",
    "RolloutCache",
    "FREQUENCY_IMMEDIATE",
    "FREQUENCY_DAILY",
    "FREQUENCY_WEEKLY",
    # Utils
    "clamp",
    "compact_dict",
    "compute_checksum",
    "consistent_hash",
    "deep_merge",
    "format_timestamp",
    "generate_id",
    "generate_trace_id",
    "is_in_rollout",
    "parse_timestamp",
    "sanitize_flag_key",
    "serialize_flag",
    # Snapshot
    "FeatureSnapshot",
    "SnapshotManager",
    # Version
    "VersionEntry",
    "VersionManager",
    # Events
    "EventBus",
    "FeatureEvent",
    "FeatureEventType",
    # Publisher
    "FeatureEventPublisher",
    # Subscriber
    "FeatureEventSubscriber",
    "SubscriberType",
    # Runtime
    "RuntimeFeatureService",
    # Hot Reload
    "HotReloadManager",
    # Protection
    "CircuitBreaker",
    "EvaluationRateLimiter",
    "PlatformProtection",
    "SnapshotIntegrityChecker",
    # Recovery
    "RecoveryManager",
    # Monitoring
    "FeatureFlagRuntimeMetrics",
    # Telemetry
    "FeatureFlagTelemetry",
    # Container
    "ServiceContainer",
    # Lifecycle
    "LifecycleState",
    "PlatformLifecycle",
    # Scheduler
    "FeatureFlagScheduler",
    # Synchronization
    "SynchronizationManager",
    # Integration
    "PlatformIntegration",
    # Bootstrap
    "FeatureFlagBootstrap",
]