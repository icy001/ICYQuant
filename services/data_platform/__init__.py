"""
ICYQuant Unified Data Platform — enterprise data infrastructure.

Provides a single unified data entry point for the entire ICYQuant platform,
integrating market connectivity, normalization, data lake, streaming,
governance, catalog, and unified APIs.

Architecture:
    Exchange → Connectivity → Normalization → [Data Lake / Streaming]
    → Unified Data Platform → Research / Strategy / Risk / OMS / EMS / AI Agent

Modules:
    - data_platform:         Unified platform entry point
    - data_runtime:          Runtime execution environment
    - data_manager:          Service lifecycle management
    - data_gateway:          Unified data access gateway
    - data_controller:       Operational control plane
    - data_orchestrator:     Cross-subsystem request orchestration
    - data_pipeline:         Unified data processing pipeline
    - connectivity_adapter:  Market connectivity subsystem adapter
    - normalization_adapter: Data normalization subsystem adapter
    - data_lake_adapter:     Historical data lake adapter
    - streaming_adapter:     Real-time streaming adapter
    - market_data_service:   Market data service
    - historical_data_service: Historical data service
    - replay_service:        Historical replay service
    - data_catalog:          Data catalog & discovery
    - metadata_service:      Metadata management
    - schema_service:        Schema management & versioning
    - data_governance:       Governance center
    - lineage_service:       Data lineage tracking
    - quality_service:       Data quality management
    - retention_service:     Data retention & lifecycle
    - data_access_control:   Enterprise access control (RBAC/ABAC)
    - permission_manager:    Role & permission management
    - audit_service:         Comprehensive audit logging
    - api_gateway:           Unified API gateway
    - sdk:                   Python Data SDK
    - api/:                  REST, gRPC, WebSocket, GraphQL endpoints
    - observability:         Platform observability
    - control_plane:         Administrative control plane
    - metrics:               Prometheus metrics
    - telemetry:             Distributed tracing
    - diagnostics:           Platform diagnostics
    - health:                Health check & circuit breaker
"""

from __future__ import annotations

# ── Core Platform ──
from services.data_platform.data_platform import (
    DataPlatform,
    PlatformConfig,
    PlatformInfo,
    PlatformStatus,
)
from services.data_platform.data_runtime import (
    DataRuntime,
    RuntimeConfig,
    RuntimeState,
)
from services.data_platform.data_manager import (
    DataManager,
    DataManagerConfig,
)
from services.data_platform.data_gateway import (
    DataGateway,
    GatewayConfig,
)
from services.data_platform.data_controller import (
    DataController,
    ControllerConfig,
)
from services.data_platform.data_orchestrator import (
    DataOrchestrator,
    OrchestratorContext,
    OrchestrationPhase,
)
from services.data_platform.data_pipeline import (
    DataPipeline,
    PipelineStage,
)

# ── Adapters ──
from services.data_platform.connectivity_adapter import ConnectivityAdapter
from services.data_platform.normalization_adapter import NormalizationAdapter
from services.data_platform.data_lake_adapter import DataLakeAdapter
from services.data_platform.streaming_adapter import StreamingAdapter

# ── Services ──
from services.data_platform.market_data_service import MarketDataService
from services.data_platform.historical_data_service import HistoricalDataService
from services.data_platform.replay_service import ReplayService

# ── Catalog & Metadata ──
from services.data_platform.data_catalog import DataCatalog
from services.data_platform.metadata_service import MetadataService
from services.data_platform.schema_service import SchemaService

# ── Governance ──
from services.data_platform.data_governance import (
    DataGovernance,
    GovernanceStatus,
    DataClassification,
    GovernancePolicy,
    GovernanceCheck,
)
from services.data_platform.lineage_service import (
    LineageService,
    LineageEvent,
    LineageEventType,
)
from services.data_platform.quality_service import (
    QualityService,
    QualityRule,
    QualityRuleType,
    QualityCheckResult,
)
from services.data_platform.retention_service import (
    RetentionService,
    RetentionPolicy,
    StorageTier,
    RetentionAction,
)

# ── Access Control ──
from services.data_platform.data_access_control import (
    DataAccessControl,
    AccessPolicy,
    AccessLevel,
    ResourceType,
)
from services.data_platform.permission_manager import (
    PermissionManager,
    Permission,
    Role,
    User,
)
from services.data_platform.audit_service import (
    AuditService,
    AuditEvent,
    AuditAction,
    AuditSeverity,
)

# ── API ──
from services.data_platform.api_gateway import (
    APIGateway,
    GatewayProtocol,
    GatewayRequest,
    GatewayResponse,
)
from services.data_platform.sdk import (
    DataSDK,
    SDKConfig,
    QueryResult,
)
from services.data_platform.api.rest import (
    DataPlatformREST,
    RESTConfig,
    APIResponse,
)
from services.data_platform.api.grpc import (
    DataPlatformGRPC,
    GRPCConfig,
    GRPCResponse,
    ServiceMethod,
)
from services.data_platform.api.websocket import (
    DataPlatformWebSocket,
    WSConfig,
    WSMessage,
    WSMessageType,
)
from services.data_platform.api.graphql import (
    DataPlatformGraphQL,
    GraphQLConfig,
    GraphQLResponse,
)

# ── Observability ──
from services.data_platform.observability import (
    DataPlatformObservability,
    ObservabilitySnapshot,
)
from services.data_platform.control_plane import (
    DataControlPlane,
    ControlAction,
    Subsystem,
    ControlCommand,
)
from services.data_platform.metrics import (
    DataPlatformMetrics,
    MetricSnapshot,
)
from services.data_platform.telemetry import (
    DataPlatformTelemetry,
    Trace,
    Span,
    TraceKind,
    SpanStatus,
)
from services.data_platform.diagnostics import (
    DataPlatformDiagnostics,
    DiagnosticResult,
)
from services.data_platform.health import (
    DataPlatformHealthChecker,
    ComponentHealth,
    HealthStatus,
)

__all__ = [
    # Core
    "DataPlatform",
    "PlatformConfig",
    "PlatformInfo",
    "PlatformStatus",
    "DataRuntime",
    "RuntimeConfig",
    "RuntimeState",
    "DataManager",
    "DataManagerConfig",
    "DataGateway",
    "GatewayConfig",
    "DataController",
    "ControllerConfig",
    "DataOrchestrator",
    "OrchestratorContext",
    "OrchestrationPhase",
    "DataPipeline",
    "PipelineStage",
    # Adapters
    "ConnectivityAdapter",
    "NormalizationAdapter",
    "DataLakeAdapter",
    "StreamingAdapter",
    # Services
    "MarketDataService",
    "HistoricalDataService",
    "ReplayService",
    # Catalog
    "DataCatalog",
    "MetadataService",
    "SchemaService",
    # Governance
    "DataGovernance",
    "GovernanceStatus",
    "DataClassification",
    "LineageService",
    "LineageEventType",
    "QualityService",
    "QualityRuleType",
    "RetentionService",
    "StorageTier",
    # Access Control
    "DataAccessControl",
    "AccessLevel",
    "PermissionManager",
    "Permission",
    "AuditService",
    "AuditAction",
    "AuditSeverity",
    # API
    "APIGateway",
    "GatewayProtocol",
    "DataSDK",
    "DataPlatformREST",
    "DataPlatformGRPC",
    "DataPlatformWebSocket",
    "DataPlatformGraphQL",
    # Observability
    "DataPlatformObservability",
    "DataControlPlane",
    "ControlAction",
    "Subsystem",
    "DataPlatformMetrics",
    "DataPlatformTelemetry",
    "TraceKind",
    "DataPlatformDiagnostics",
    "DataPlatformHealthChecker",
    "HealthStatus",
]
