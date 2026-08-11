"""
ICYQuant Production Strategy Platform
======================================
Unified control plane, platform integration, and governance
for production trading strategies.

This package provides the final integration layer that connects
the Strategy Platform to all other ICYQuant subsystems through
standardized adapters, APIs, and event-driven architecture.
"""

from services.strategy.platform.strategy_platform import (
    StrategyPlatform,
    PlatformConfig,
    PlatformStatus,
)

from services.strategy.platform.control_plane import (
    ControlPlane,
    ControlCommand,
    ControlResult,
)

from services.strategy.platform.strategy_gateway import (
    StrategyGateway,
    GatewayConfig,
    GatewayRoute,
    GatewayRequest,
    GatewayResponse,
)

from services.strategy.platform.lifecycle_controller import (
    LifecycleController,
    LifecycleAction,
    LifecycleTransition,
    LifecycleState,
)

from services.strategy.platform.deployment_manager import (
    DeploymentManager,
    DeploymentStatus,
    DeploymentPackage,
    DeploymentTarget,
)

from services.strategy.platform.release_manager import (
    ReleaseManager,
    ReleaseStatus,
    ReleaseArtifact,
    ReleaseChannel,
)

from services.strategy.platform.rollout_manager import (
    RolloutManager,
    RolloutStage,
    RolloutProgress,
)

from services.strategy.platform.canary_manager import (
    CanaryManager,
    CanaryStage,
    CanaryConfig,
    CanaryMetrics,
)

from services.strategy.platform.rollback_manager import (
    RollbackManager,
    RollbackStrategy,
    RollbackSnapshot,
    RollbackResult,
)

from services.strategy.platform.strategy_catalog import (
    StrategyCatalog,
    CatalogEntry,
    CatalogQuery,
)

from services.strategy.platform.strategy_directory import (
    StrategyDirectory,
    DirectoryEntry,
    DirectoryFilter,
)

from services.strategy.platform.dependency_manager import (
    DependencyManager,
    DependencyGraph,
    DependencyNode,
    DependencyStatus,
)

from services.strategy.platform.feature_store_adapter import (
    FeatureStoreAdapter,
    FeatureRequest,
    FeatureResult,
)

from services.strategy.platform.market_data_adapter import (
    MarketDataAdapter,
    MarketDataRequest,
    MarketDataSnapshot,
)

from services.strategy.platform.workflow_adapter import (
    WorkflowAdapter,
    WorkflowTrigger,
    WorkflowStatus,
)

from services.strategy.platform.scheduler_adapter import (
    SchedulerAdapter,
    ScheduleDefinition,
    ScheduleStatus,
)

from services.strategy.platform.research_adapter import (
    ResearchAdapter,
    ResearchTask,
    ResearchResult,
)

from services.strategy.platform.risk_engine_adapter import (
    RiskEngineAdapter,
    RiskCheckRequest,
    RiskCheckResult,
)

from services.strategy.platform.oms_adapter import (
    OMSAdapter,
    OMSOrderRequest,
    OMSOrderResult,
)

from services.strategy.platform.ems_adapter import (
    EMSAdapter,
    EMSExecutionRequest,
    EMSExecutionResult,
)

from services.strategy.platform.monitoring_adapter import (
    MonitoringAdapter,
    MonitorMetric,
    MonitorAlert,
)

from services.strategy.platform.event_bridge import (
    EventBridge,
    StrategyEvent,
    EventType,
    EventPriority,
)

from services.strategy.platform.event_stream import (
    EventStream,
    StreamSubscription,
    StreamMessage,
)

from services.strategy.platform.audit_center import (
    AuditCenter,
    AuditRecord,
    AuditCategory,
    AuditLevel,
)

from services.strategy.platform.observability import (
    StrategyObservability,
    ObservabilityReport,
    ObservabilityLevel,
)

from services.strategy.platform.trace_manager import (
    TraceManager,
    TraceSpan,
    TraceContext,
)

from services.strategy.platform.sdk import (
    StrategySDK,
    SDKContext,
    SDKConfig,
)

from services.strategy.platform.rest_api import (
    StrategyRESTAPI,
    RESTEndpoint,
    RESTResponse,
)

from services.strategy.platform.grpc_api import (
    StrategyGRPCAPI,
    GRPCService,
    GRPCMethod,
)

from services.strategy.platform.websocket_api import (
    StrategyWebSocketAPI,
    WSConnection,
    WSChannel,
    WSMessage,
)

from services.strategy.platform.metrics import PlatformMetrics

from services.strategy.platform.telemetry import PlatformTelemetry

from services.strategy.platform.diagnostics import (
    PlatformDiagnostics,
    PlatformDiagnosticReport,
)

from services.strategy.platform.health import PlatformHealthChecker

__all__ = [
    # Core Platform
    "StrategyPlatform",
    "PlatformConfig",
    "PlatformStatus",
    "ControlPlane",
    "ControlCommand",
    "ControlResult",
    "StrategyGateway",
    "GatewayConfig",
    "GatewayRoute",
    "GatewayRequest",
    "GatewayResponse",
    "LifecycleController",
    "LifecycleAction",
    "LifecycleTransition",
    "LifecycleState",
    # Deployment
    "DeploymentManager",
    "DeploymentStatus",
    "DeploymentPackage",
    "DeploymentTarget",
    "ReleaseManager",
    "ReleaseStatus",
    "ReleaseArtifact",
    "ReleaseChannel",
    "RolloutManager",
    "RolloutStage",
    "RolloutProgress",
    "CanaryManager",
    "CanaryStage",
    "CanaryConfig",
    "CanaryMetrics",
    "RollbackManager",
    "RollbackStrategy",
    "RollbackSnapshot",
    "RollbackResult",
    # Catalog
    "StrategyCatalog",
    "CatalogEntry",
    "CatalogQuery",
    "StrategyDirectory",
    "DirectoryEntry",
    "DirectoryFilter",
    "DependencyManager",
    "DependencyGraph",
    "DependencyNode",
    "DependencyStatus",
    # Adapters
    "FeatureStoreAdapter",
    "FeatureRequest",
    "FeatureResult",
    "MarketDataAdapter",
    "MarketDataRequest",
    "MarketDataSnapshot",
    "WorkflowAdapter",
    "WorkflowTrigger",
    "WorkflowStatus",
    "SchedulerAdapter",
    "ScheduleDefinition",
    "ScheduleStatus",
    "ResearchAdapter",
    "ResearchTask",
    "ResearchResult",
    "RiskEngineAdapter",
    "RiskCheckRequest",
    "RiskCheckResult",
    "OMSAdapter",
    "OMSOrderRequest",
    "OMSOrderResult",
    "EMSAdapter",
    "EMSExecutionRequest",
    "EMSExecutionResult",
    "MonitoringAdapter",
    "MonitorMetric",
    "MonitorAlert",
    # Events & Audit
    "EventBridge",
    "StrategyEvent",
    "EventType",
    "EventPriority",
    "EventStream",
    "StreamSubscription",
    "StreamMessage",
    "AuditCenter",
    "AuditRecord",
    "AuditCategory",
    "AuditLevel",
    # Observability
    "StrategyObservability",
    "ObservabilityReport",
    "ObservabilityLevel",
    "TraceManager",
    "TraceSpan",
    "TraceContext",
    # API & SDK
    "StrategySDK",
    "SDKContext",
    "SDKConfig",
    "StrategyRESTAPI",
    "RESTEndpoint",
    "RESTResponse",
    "StrategyGRPCAPI",
    "GRPCService",
    "GRPCMethod",
    "StrategyWebSocketAPI",
    "WSConnection",
    "WSChannel",
    "WSMessage",
    # Metrics & Health
    "PlatformMetrics",
    "PlatformTelemetry",
    "PlatformDiagnostics",
    "PlatformDiagnosticReport",
    "PlatformHealthChecker",
]
