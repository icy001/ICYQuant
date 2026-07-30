"""ICYQuant Institutional Data Platform.

Enterprise-grade data infrastructure providing:
    - Data Lakehouse (hot/warm/cold tiering, time-travel)
    - Unified Data Fabric (single source of truth)
    - Metadata Catalog (searchable data asset registry)
    - Schema Registry (versioned schema management)
    - Data Lineage (end-to-end provenance tracking)
    - Quality Engine (automated data validation)
    - Governance Engine (ownership, classification, compliance)
    - Access Controller (RBAC permissions)
    - Version Manager (snapshots and point-in-time recovery)
    - Time Travel (historical data queries)
    - Partition Manager (partitioned storage)
    - Lifecycle Manager (tier transitions, cost optimization)

Usage::

    from services.data_platform import DataPlatformService, DataPlatformConfig

    svc = DataPlatformService(DataPlatformConfig())
    svc.initialize()
    svc.ingest("market_tick", data, producer="market_data")
    result = svc.query("market_tick", consumer="research")
"""

from services.data_platform.config import (
    DataPlatformConfig,
    LakehouseConfig,
    CatalogConfig,
    SchemaRegistryConfig,
    LineageConfig,
    QualityConfig,
    GovernanceConfig,
    AccessControlConfig,
    VersionConfig,
    TimeTravelConfig,
    PartitionConfig,
    LifecycleConfig,
    StorageTier,
    DataClassification,
    QualityRuleType,
    AccessLevel,
    SchemaCompatibility,
    PartitionType,
    LifecycleAction,
    SnapshotFrequency,
    CatalogEntryType,
)
from services.data_platform.lakehouse import (
    DataLakehouse,
    DatasetSchema,
    DatasetType,
    WriteMode,
    DataFile,
    TableSnapshot,
)
from services.data_platform.data_fabric import (
    DataFabric,
    FabricQuery,
    FabricWriteRequest,
    FabricResult,
    FabricAccessPattern,
    DataView,
)
from services.data_platform.metadata_catalog import (
    MetadataCatalog,
    CatalogEntry,
    ColumnMetadata,
    DatasetStatistics,
    SearchResult,
)
from services.data_platform.schema_registry import (
    SchemaRegistry,
    SchemaDefinition,
    FieldDefinition,
    FieldType,
    CompatibilityReport,
    ValidationResult,
)
from services.data_platform.lineage import (
    LineageTracker,
    LineageNode,
    LineageEdge,
    LineageChain,
    OperationType,
    ImpactAnalysis,
)
from services.data_platform.quality_engine import (
    QualityEngine,
    QualityRule,
    QualityReport,
    NotNullRule,
    UniqueRule,
    RangeRule,
    EnumRule,
    RegexRule,
    CustomRule,
    TimelinessRule,
)
from services.data_platform.governance import (
    GovernanceEngine,
    DataOwner,
    RetentionPolicy,
    ComplianceReport,
    AuditEntry,
)
from services.data_platform.access_controller import (
    AccessController,
    AccessDecision,
    UserAccess,
    Role,
    AccessRequest,
)
from services.data_platform.version_manager import (
    VersionManager,
    VersionInfo,
    SnapshotDiff,
)
from services.data_platform.time_travel import (
    TimeTravel,
    TimeTravelResult,
    TimeBranch,
    TimeTag,
)
from services.data_platform.partition_manager import (
    PartitionManager,
    PartitionInfo,
    PartitionSpec,
    CompactionResult,
)
from services.data_platform.lifecycle import (
    LifecycleManager,
    LifecyclePolicy,
    LifecycleReport,
    TierTransition,
    CostEstimate,
)
from services.data_platform.service import DataPlatformService
from services.data_platform.api.data_platform_api import (
    DataPlatformAPI,
    APIResponse,
    IngestRequest,
    QueryRequest,
    TimeTravelRequest,
    SnapshotRequest,
    SchemaRegisterRequest,
)

__all__ = [
    # Config
    "DataPlatformConfig", "LakehouseConfig", "CatalogConfig",
    "SchemaRegistryConfig", "LineageConfig", "QualityConfig",
    "GovernanceConfig", "AccessControlConfig", "VersionConfig",
    "TimeTravelConfig", "PartitionConfig", "LifecycleConfig",
    # Enums
    "StorageTier", "DataClassification", "QualityRuleType",
    "AccessLevel", "SchemaCompatibility", "PartitionType",
    "LifecycleAction", "SnapshotFrequency", "CatalogEntryType",
    "DatasetType", "WriteMode", "FabricAccessPattern", "OperationType",
    "FieldType",
    # Lakehouse
    "DataLakehouse", "DatasetSchema", "DataFile", "TableSnapshot",
    # Data Fabric
    "DataFabric", "FabricQuery", "FabricWriteRequest", "FabricResult", "DataView",
    # Metadata Catalog
    "MetadataCatalog", "CatalogEntry", "ColumnMetadata",
    "DatasetStatistics", "SearchResult",
    # Schema Registry
    "SchemaRegistry", "SchemaDefinition", "FieldDefinition",
    "CompatibilityReport", "ValidationResult",
    # Lineage
    "LineageTracker", "LineageNode", "LineageEdge", "LineageChain", "ImpactAnalysis",
    # Quality Engine
    "QualityEngine", "QualityRule", "QualityReport",
    "NotNullRule", "UniqueRule", "RangeRule", "EnumRule",
    "RegexRule", "CustomRule", "TimelinessRule",
    # Governance
    "GovernanceEngine", "DataOwner", "RetentionPolicy",
    "ComplianceReport", "AuditEntry",
    # Access Control
    "AccessController", "AccessDecision", "UserAccess", "Role", "AccessRequest",
    # Versioning
    "VersionManager", "VersionInfo", "SnapshotDiff",
    # Time Travel
    "TimeTravel", "TimeTravelResult", "TimeBranch", "TimeTag",
    # Partition
    "PartitionManager", "PartitionInfo", "PartitionSpec", "CompactionResult",
    # Lifecycle
    "LifecycleManager", "LifecyclePolicy", "LifecycleReport",
    "TierTransition", "CostEstimate",
    # Service & API
    "DataPlatformService", "DataPlatformAPI", "APIResponse",
    "IngestRequest", "QueryRequest", "TimeTravelRequest",
    "SnapshotRequest", "SchemaRegisterRequest",
]
