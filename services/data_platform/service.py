"""ICYQuant Data Platform Service.

Unified orchestrator for the institutional data platform.
Coordinates all subsystems:
    - Lakehouse
    - Data Fabric
    - Metadata Catalog
    - Schema Registry
    - Data Lineage
    - Quality Engine
    - Governance Engine
    - Access Controller
    - Version Manager
    - Time Travel
    - Partition Manager
    - Lifecycle Manager

Usage::

    svc = DataPlatformService(DataPlatformConfig())
    svc.ingest("market_tick", data, producer="market_data")
    result = svc.query("market_tick", consumer="research")
    catalog = svc.search_catalog("tick")
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from services.data_platform.config import (
    DataPlatformConfig,
    AccessLevel,
    DataClassification,
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
    CatalogEntryType,
    SearchResult,
)
from services.data_platform.schema_registry import (
    SchemaRegistry,
    SchemaDefinition,
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
    QualityReport,
    QualityRule,
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
    CostEstimate,
)


class DataPlatformService:
    """ICYQuant Data Platform Service.

    Unified orchestrator that initializes and coordinates all data
    platform subsystems. Provides high-level operations for data
    ingestion, querying, cataloging, quality, governance, and lifecycle.

    Usage::

        svc = DataPlatformService(DataPlatformConfig())
        svc.initialize()

        # Ingest data
        svc.ingest("market_tick", tick_data, producer="market_data")

        # Query data
        result = svc.query("market_tick", consumer="research")

        # Search catalog
        results = svc.search_catalog("tick")

        # Get lineage
        chain = svc.trace_lineage("market_tick")
    """

    def __init__(self, config: Optional[DataPlatformConfig] = None) -> None:
        self.config = config or DataPlatformConfig()

        # Initialize subsystems
        self.lakehouse = DataLakehouse(self.config.lakehouse)
        self.quality_engine = QualityEngine(self.config.quality)
        self.lineage_tracker = LineageTracker(self.config.lineage)
        self.fabric = DataFabric(
            self.lakehouse,
            self.quality_engine,
            self.lineage_tracker,
            self.config.lakehouse,
        )
        self.catalog = MetadataCatalog(self.config.catalog)
        self.schema_registry = SchemaRegistry(self.config.schema_registry)
        self.governance = GovernanceEngine(self.config.governance)
        self.access_controller = AccessController(self.config.access_control)
        self.version_manager = VersionManager(self.config.versioning, self.lakehouse)
        self.time_travel = TimeTravel(self.config.time_travel, self.lakehouse)
        self.partition_manager = PartitionManager(self.config.partition, self.lakehouse)
        self.lifecycle_manager = LifecycleManager(self.config.lifecycle, self.lakehouse)

        self._initialized = False

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Initialize the data platform and register default assets."""
        if self._initialized:
            return

        # Register common schemas
        self._register_default_schemas()
        self._initialized = True

    def _register_default_schemas(self) -> None:
        """Register default schemas for common data types."""
        from services.data_platform.schema_registry import FieldDefinition, FieldType

        # Tick schema
        tick_schema = SchemaDefinition(
            name="market_tick",
            version=1,
            description="Market tick data schema",
            fields=[
                FieldDefinition("symbol", FieldType.STRING, required=True),
                FieldDefinition("timestamp", FieldType.TIMESTAMP, required=True),
                FieldDefinition("bid", FieldType.FLOAT, required=True),
                FieldDefinition("ask", FieldType.FLOAT, required=True),
                FieldDefinition("bid_volume", FieldType.INTEGER),
                FieldDefinition("ask_volume", FieldType.INTEGER),
                FieldDefinition("last_price", FieldType.FLOAT),
                FieldDefinition("volume", FieldType.INTEGER),
            ],
            primary_key=["symbol", "timestamp"],
        )
        self.schema_registry.register("market_tick", tick_schema)

        # Bar schema
        bar_schema = SchemaDefinition(
            name="market_bar",
            version=1,
            description="OHLCV bar data schema",
            fields=[
                FieldDefinition("symbol", FieldType.STRING, required=True),
                FieldDefinition("timestamp", FieldType.TIMESTAMP, required=True),
                FieldDefinition("open", FieldType.FLOAT, required=True),
                FieldDefinition("high", FieldType.FLOAT, required=True),
                FieldDefinition("low", FieldType.FLOAT, required=True),
                FieldDefinition("close", FieldType.FLOAT, required=True),
                FieldDefinition("volume", FieldType.INTEGER, required=True),
            ],
            primary_key=["symbol", "timestamp"],
        )
        self.schema_registry.register("market_bar", bar_schema)

    # ------------------------------------------------------------------
    # Data Ingestion
    # ------------------------------------------------------------------

    def ingest(
        self,
        dataset: str,
        data: List[Dict[str, Any]],
        producer: str = "default",
        mode: WriteMode = WriteMode.APPEND,
        validate_quality: bool = True,
    ) -> FabricResult:
        """Ingest data into the platform.

        Applies quality checks, tracks lineage, and writes to lakehouse
        through the data fabric.

        Args:
            dataset: Target dataset name.
            data: Data records to ingest.
            producer: Producer identifier.
            mode: Write mode.
            validate_quality: Run quality checks before ingest.

        Returns:
            FabricResult.
        """
        return self.fabric.write(FabricWriteRequest(
            dataset=dataset,
            data=data,
            producer=producer,
            mode=mode,
            validate_quality=validate_quality,
        ))

    def query(
        self,
        dataset: str,
        consumer: str = "default",
        as_of: Optional[datetime] = None,
        partition: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> FabricResult:
        """Query data from the platform through the data fabric.

        Args:
            dataset: Dataset name.
            consumer: Consumer identifier.
            as_of: Point-in-time for time travel.
            partition: Partition filter.
            filters: Row-level filters.
            limit: Maximum records.

        Returns:
            FabricResult.
        """
        return self.fabric.query(FabricQuery(
            dataset=dataset,
            consumer=consumer,
            as_of=as_of,
            partition=partition,
            filters=filters or {},
            limit=limit,
        ))

    # ------------------------------------------------------------------
    # Catalog Operations
    # ------------------------------------------------------------------

    def register_in_catalog(
        self,
        name: str,
        entry_type: CatalogEntryType,
        owner: str = "",
        description: str = "",
        **kwargs: Any,
    ) -> CatalogEntry:
        """Register a data asset in the metadata catalog.

        Args:
            name: Asset name.
            entry_type: Type of catalog entry.
            owner: Asset owner.
            description: Description.
            **kwargs: Additional entry fields.

        Returns:
            CatalogEntry.
        """
        entry = CatalogEntry(
            name=name,
            entry_type=entry_type,
            owner=owner,
            description=description,
            **kwargs,
        )
        return self.catalog.register(name, entry)

    def search_catalog(self, query: str, **kwargs: Any) -> SearchResult:
        """Search the metadata catalog.

        Args:
            query: Search query.
            **kwargs: Additional search filters.

        Returns:
            SearchResult.
        """
        return self.catalog.search(query, **kwargs)

    # ------------------------------------------------------------------
    # Lineage Operations
    # ------------------------------------------------------------------

    def trace_lineage(self, dataset: str, direction: str = "downstream") -> LineageChain:
        """Trace data lineage.

        Args:
            dataset: Dataset name.
            direction: "downstream" or "upstream".

        Returns:
            LineageChain.
        """
        if direction == "upstream":
            return self.lineage_tracker.trace_upstream(dataset)
        return self.lineage_tracker.trace_downstream(dataset)

    def analyze_impact(self, dataset: str) -> ImpactAnalysis:
        """Analyze impact of changing a dataset.

        Args:
            dataset: Dataset name.

        Returns:
            ImpactAnalysis.
        """
        return self.lineage_tracker.analyze_impact(dataset)

    # ------------------------------------------------------------------
    # Quality Operations
    # ------------------------------------------------------------------

    def check_quality(self, dataset: str, data: List[Dict[str, Any]]) -> QualityReport:
        """Run quality checks on data.

        Args:
            dataset: Dataset name.
            data: Data to validate.

        Returns:
            QualityReport.
        """
        return self.quality_engine.validate(dataset, data)

    def add_quality_rule(self, dataset: str, rule: QualityRule) -> None:
        """Add a quality rule for a dataset.

        Args:
            dataset: Dataset name.
            rule: QualityRule to add.
        """
        self.quality_engine.add_rule(dataset, rule)

    # ------------------------------------------------------------------
    # Governance Operations
    # ------------------------------------------------------------------

    def assign_data_owner(
        self, dataset: str, owner: str, team: str = ""
    ) -> DataOwner:
        """Assign a data owner.

        Args:
            dataset: Dataset name.
            owner: Owner identifier.
            team: Team name.

        Returns:
            DataOwner.
        """
        return self.governance.assign_owner(dataset, owner, team=team)

    def classify_data(
        self, dataset: str, classification: DataClassification
    ) -> None:
        """Classify a dataset.

        Args:
            dataset: Dataset name.
            classification: Data classification level.
        """
        self.governance.set_classification(dataset, classification)

    def check_compliance(self, dataset: str) -> ComplianceReport:
        """Check governance compliance for a dataset.

        Args:
            dataset: Dataset name.

        Returns:
            ComplianceReport.
        """
        return self.governance.check_compliance(dataset)

    # ------------------------------------------------------------------
    # Access Control Operations
    # ------------------------------------------------------------------

    def check_access(
        self, user_id: str, dataset: str, action: str
    ) -> AccessDecision:
        """Check if a user has access to perform an action.

        Args:
            user_id: User identifier.
            dataset: Dataset name.
            action: Action string (read, write, etc.).

        Returns:
            AccessDecision.
        """
        return self.access_controller.check_permission(user_id, dataset, action)

    def assign_role(self, user_id: str, role_name: str) -> bool:
        """Assign a role to a user.

        Args:
            user_id: User identifier.
            role_name: Role name.

        Returns:
            True if assigned.
        """
        return self.access_controller.assign_role(user_id, role_name)

    # ------------------------------------------------------------------
    # Version & Snapshot Operations
    # ------------------------------------------------------------------

    def create_version(
        self, dataset: str, description: str = ""
    ) -> VersionInfo:
        """Create a versioned snapshot of a dataset.

        Args:
            dataset: Dataset name.
            description: Version description.

        Returns:
            VersionInfo.
        """
        return self.version_manager.create_version(dataset, description)

    def restore_version(self, dataset: str, version_id: str) -> bool:
        """Restore a dataset to a previous version.

        Args:
            dataset: Dataset name.
            version_id: Version ID.

        Returns:
            True if restored.
        """
        return self.version_manager.restore_version(dataset, version_id)

    # ------------------------------------------------------------------
    # Time Travel Operations
    # ------------------------------------------------------------------

    def query_as_of(
        self, dataset: str, timestamp: datetime
    ) -> TimeTravelResult:
        """Time-travel query.

        Args:
            dataset: Dataset name.
            timestamp: Point-in-time.

        Returns:
            TimeTravelResult.
        """
        return self.time_travel.query_as_of(dataset, timestamp)

    def create_time_tag(
        self, name: str, dataset: str, timestamp: datetime
    ) -> TimeTag:
        """Create a named time tag.

        Args:
            name: Tag name.
            dataset: Dataset name.
            timestamp: Point-in-time.

        Returns:
            TimeTag.
        """
        return self.time_travel.tag(name, dataset, timestamp)

    # ------------------------------------------------------------------
    # Lifecycle Operations
    # ------------------------------------------------------------------

    def add_lifecycle_policy(
        self,
        name: str,
        dataset: str,
        hot_days: int = 30,
        warm_days: int = 90,
        cold_days: int = 365,
    ) -> LifecyclePolicy:
        """Add a lifecycle policy.

        Args:
            name: Policy name.
            dataset: Dataset name.
            hot_days: Days in hot tier.
            warm_days: Days in warm tier.
            cold_days: Days in cold tier.

        Returns:
            LifecyclePolicy.
        """
        return self.lifecycle_manager.add_policy(
            name, dataset,
            hot_retention_days=hot_days,
            warm_retention_days=warm_days,
            cold_retention_days=cold_days,
        )

    def apply_lifecycle_policies(self) -> List[LifecycleReport]:
        """Apply all lifecycle policies.

        Returns:
            List of LifecycleReport.
        """
        return self.lifecycle_manager.apply_all_policies()

    # ------------------------------------------------------------------
    # Platform Statistics
    # ------------------------------------------------------------------

    def get_platform_stats(self) -> Dict[str, Any]:
        """Get comprehensive platform statistics.

        Returns:
            Dict with all subsystem stats.
        """
        return {
            "lakehouse": self.lakehouse.get_storage_stats(),
            "catalog": self.catalog.get_catalog_stats(),
            "lineage": self.lineage_tracker.get_graph_stats(),
            "quality": self.quality_engine.get_overall_stats(),
            "governance": self.governance.get_compliance_summary(),
            "access_control": self.access_controller.get_access_stats(),
            "versioning": self.version_manager.get_stats(),
            "time_travel": self.time_travel.get_stats(),
            "partition": self.partition_manager.get_stats(),
            "lifecycle": self.lifecycle_manager.get_stats(),
        }

    def get_platform_health(self) -> Dict[str, Any]:
        """Get platform health status.

        Returns:
            Dict with health indicators.
        """
        storage = self.lakehouse.get_storage_stats()
        quality = self.quality_engine.get_overall_stats()

        return {
            "status": "healthy",
            "storage": {
                "total_gb": round(storage["total_size_bytes"] / (1024 ** 3), 2),
                "dataset_count": storage["dataset_count"],
            },
            "quality_score": quality["average_quality_score"],
            "catalog_entries": self.catalog.get_catalog_stats()["total_entries"],
            "lineage_nodes": self.lineage_tracker.get_graph_stats()["total_nodes"],
        }
