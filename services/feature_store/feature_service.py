"""Feature Service — unified orchestrator for the Feature Store.

Provides a single entry point for all feature store operations,
combining registry, catalog, versioning, lineage, validation,
monitoring, online store, and offline store.

Usage::

    from services.feature_store import FeatureService

    svc = FeatureService()
    svc.register_feature("ema20", version="v1", owner="research")
    svc.publish_feature("ema20", "v1")
    svc.set_online("NVDA", {"ema20": 182.31})
    value = svc.get_online_feature("NVDA", "ema20")
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.feature_store.config import FeatureStoreConfig
from services.feature_store.registry import FeatureDefinition, FeatureRegistry, FeatureStatus
from services.feature_store.catalog import FeatureCatalog, FeatureCategory
from services.feature_store.lineage import FeatureLineage, LineageGraph, LineageNode, NodeType
from services.feature_store.versioning import FeatureVersion, FeatureVersioning, VersionStage
from services.feature_store.validator import FeatureValidator, ValidationReport, ValidationRule
from services.feature_store.monitor import DriftReport, DriftStatus, FeatureMonitor, MonitoringConfig
from services.feature_store.online_store import OnlineFeatureRecord, OnlineFeatureStore, StoreTTL
from services.feature_store.offline_store import OfflineDataset, OfflineFeatureStore, OfflineQuery, PartitionUnit


class FeatureService:
    """Unified orchestrator for all feature store operations.

    Composes all feature store sub-systems into a single
    service facade for convenient use in research, training,
    backtesting, and inference pipelines.

    Lifecycle::

        register -> validate -> version -> publish -> online/offline -> monitor
    """

    # ---- 分组：初始化 ----

    def __init__(self, config: Optional[FeatureStoreConfig] = None) -> None:
        """Initialize the feature service.

        Args:
            config: Optional feature store configuration.
        """
        self.config = config or FeatureStoreConfig()
        self.registry = FeatureRegistry()
        self.catalog = FeatureCatalog()
        self.versioning = FeatureVersioning()
        self.lineage = FeatureLineage()
        self.validator = FeatureValidator()
        self.monitor = FeatureMonitor()
        self.online_store = OnlineFeatureStore()
        self.offline_store = OfflineFeatureStore(self.config.local_offline_path)

    # ---- 分组：特征注册 ----

    def register_feature(
        self,
        feature_name: str,
        version: str = "v1",
        owner: Optional[str] = None,
        dtype: str = "float64",
        frequency: str = "1d",
        description: str = "",
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source: str = "",
    ) -> FeatureDefinition:
        """Register a new feature in the registry.

        Args:
            feature_name: Unique feature identifier.
            version: Version string.
            owner: Responsible team.
            dtype: Data type.
            frequency: Data frequency.
            description: Human-readable description.
            category: Logical category.
            tags: Searchable tags.
            source: Upstream data source.

        Returns:
            The registered FeatureDefinition.
        """
        definition = FeatureDefinition(
            feature_name=feature_name,
            version=version,
            owner=owner or self.config.default_owner,
            dtype=dtype,
            frequency=frequency or self.config.default_frequency,
            description=description,
            category=category or "uncategorized",
            tags=tags or [],
            source=source,
        )

        registered = self.registry.register(definition)

        # Auto-assign to category if provided
        if category:
            if category not in [c.name for c in self.catalog.list_categories()]:
                self.catalog.create_category(category)
            self.catalog.assign(feature_name, category)

        return registered

    # ---- 分组：特征版本管理 ----

    def publish_feature(
        self,
        feature_name: str,
        version: str,
        changelog: str = "",
        definition: Optional[Dict[str, Any]] = None,
    ) -> FeatureVersion:
        """Publish a feature version to the versioning system.

        Args:
            feature_name: Feature identifier.
            version: Version string.
            changelog: Description of changes.
            definition: Feature computation definition.

        Returns:
            The created FeatureVersion.
        """
        # Create version entry
        fv = self.versioning.create(
            feature_name=feature_name,
            version=version,
            definition=definition or {},
            changelog=changelog,
        )
        # Promote to active
        self.versioning.promote(feature_name, version, VersionStage.ACTIVE)
        return fv

    def get_active_feature_version(self, feature_name: str) -> Optional[FeatureVersion]:
        """Get the currently active version of a feature.

        Args:
            feature_name: Feature identifier.

        Returns:
            Active FeatureVersion or None.
        """
        return self.versioning.get_active(feature_name)

    # ---- 分组：在线特征 ----

    def set_online(
        self,
        entity_id: str,
        features: Dict[str, float],
        ttl: Optional[StoreTTL] = None,
    ) -> OnlineFeatureRecord:
        """Set feature values in the online store.

        Args:
            entity_id: Entity identifier.
            features: Feature name -> value mapping.
            ttl: Optional TTL override.

        Returns:
            The stored OnlineFeatureRecord.
        """
        return self.online_store.set(entity_id, features, ttl=ttl)

    def get_online_feature(self, entity_id: str, feature_name: str) -> Optional[float]:
        """Get a single feature value from the online store.

        Args:
            entity_id: Entity identifier.
            feature_name: Feature name.

        Returns:
            Feature value or None.
        """
        return self.online_store.get_feature(entity_id, feature_name)

    def get_online_features(self, entity_id: str) -> Optional[Dict[str, float]]:
        """Get all features for an entity from the online store.

        Args:
            entity_id: Entity identifier.

        Returns:
            Feature dict or None.
        """
        return self.online_store.get(entity_id)

    def batch_get_online(self, entity_ids: List[str]) -> Dict[str, Dict[str, float]]:
        """Batch get online features.

        Args:
            entity_ids: List of entity identifiers.

        Returns:
            Dict of entity_id -> feature_dict.
        """
        return self.online_store.batch_get(entity_ids)

    # ---- 分组：离线特征 ----

    def write_offline(
        self,
        feature_name: str,
        partition_key: str,
        rows: List[Dict[str, Any]],
        partition_unit: PartitionUnit = PartitionUnit.MONTH,
    ) -> OfflineDataset:
        """Write feature data to the offline store.

        Args:
            feature_name: Feature name.
            partition_key: Partition identifier.
            rows: Data rows.
            partition_unit: Partition granularity.

        Returns:
            OfflineDataset metadata.
        """
        return self.offline_store.write(feature_name, partition_key, rows, partition_unit)

    def read_offline(
        self,
        feature_name: str,
        partition_key: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        entity_ids: Optional[List[str]] = None,
        columns: Optional[List[str]] = None,
        limit: int = 100000,
    ) -> List[Dict[str, Any]]:
        """Read feature data from the offline store.

        Args:
            feature_name: Feature name.
            partition_key: Specific partition.
            start_time: Start of time range.
            end_time: End of time range.
            entity_ids: Entity filter.
            columns: Column filter.
            limit: Max rows.

        Returns:
            List of row dicts.
        """
        return self.offline_store.read(
            feature_name, partition_key, start_time, end_time, entity_ids, columns, limit
        )

    # ---- 分组：校验 ----

    def validate_feature(
        self,
        feature_name: str,
        values: List[float],
        timestamps: Optional[List[float]] = None,
        version: str = "v1",
        reference_timestamps: Optional[List[float]] = None,
    ) -> ValidationReport:
        """Validate feature data quality.

        Args:
            feature_name: Feature name.
            values: Feature values.
            timestamps: Optional timestamps.
            version: Feature version.
            reference_timestamps: Reference for lookahead bias check.

        Returns:
            ValidationReport.
        """
        return self.validator.validate(
            feature_name=feature_name,
            values=values,
            timestamps=timestamps,
            version=version,
            reference_timestamps=reference_timestamps,
        )

    # ---- 分组：漂移监控 ----

    def check_drift(
        self,
        feature_name: str,
        training_values: List[float],
        production_values: List[float],
    ) -> DriftReport:
        """Check for feature drift.

        Args:
            feature_name: Feature name.
            training_values: Training distribution values.
            production_values: Production distribution values.

        Returns:
            DriftReport.
        """
        return self.monitor.check_drift(feature_name, training_values, production_values)

    def get_drift_status(self, feature_name: str) -> Optional[DriftStatus]:
        """Get the latest drift status for a feature.

        Args:
            feature_name: Feature name.

        Returns:
            DriftStatus or None.
        """
        return self.monitor.get_latest_status(feature_name)

    def list_drifted_features(self) -> List[str]:
        """List features currently in drift/warning state.

        Returns:
            Sorted list of feature names.
        """
        return self.monitor.list_drifted_features()

    # ---- 分组：血缘 ----

    def track_lineage(
        self,
        node_id: str,
        node_type: NodeType = NodeType.FEATURE,
        parents: Optional[List[str]] = None,
        description: str = "",
    ) -> LineageNode:
        """Add a lineage node and connect to parents.

        Args:
            node_id: Node identifier.
            node_type: Node type.
            parents: Upstream node IDs.
            description: Human-readable description.

        Returns:
            The created LineageNode.
        """
        node = self.lineage.add_node(node_id, node_type, description)
        if parents:
            for parent in parents:
                if parent in self.lineage._nodes:
                    self.lineage.add_edge(parent, node_id)
        return node

    def get_feature_lineage(self, feature_name: str) -> Optional[LineageGraph]:
        """Get the lineage subgraph for a feature.

        Args:
            feature_name: Feature name.

        Returns:
            LineageGraph or None if feature not tracked.
        """
        if feature_name not in self.lineage._nodes:
            return None
        return self.lineage.get_subgraph(feature_name, "upstream")

    def get_downstream_impact(self, feature_name: str) -> List[str]:
        """Get features/models impacted by a feature change.

        Args:
            feature_name: Feature name.

        Returns:
            List of downstream node IDs.
        """
        if feature_name not in self.lineage._nodes:
            return []
        return self.lineage.get_downstream(feature_name)

    # ---- 分组：分类 ----

    def create_category(self, name: str, description: str = "", parent: Optional[str] = None) -> FeatureCategory:
        """Create a feature category.

        Args:
            name: Category name.
            description: Category description.
            parent: Optional parent category.

        Returns:
            The created FeatureCategory.
        """
        return self.catalog.create_category(name, description, parent)

    def get_category_tree(self) -> Dict[str, object]:
        """Get the hierarchical category tree.

        Returns:
            Nested dict of categories.
        """
        return self.catalog.get_tree()

    # ---- 分组：统计 ----

    def stats(self) -> Dict[str, Any]:
        """Get aggregate feature store statistics.

        Returns:
            Dict with counts across all sub-systems.
        """
        return {
            "registry": {
                "feature_count": len(self.registry.feature_names()),
                "version_count": self.registry.count(),
                "active_count": len(self.registry.list_active()),
            },
            "catalog": {
                "category_count": len(self.catalog.list_categories()),
            },
            "lineage": {
                "node_count": self.lineage.node_count(),
                "edge_count": self.lineage.edge_count(),
            },
            "online_store": {
                "entity_count": self.online_store.entity_count(),
                "feature_count": self.online_store.feature_count(),
            },
            "offline_store": {
                "feature_count": len(self.offline_store.list_features()),
                "partition_count": self.offline_store.total_partitions(),
                "total_rows": self.offline_store.total_rows(),
            },
            "monitor": {
                "drifted_features": len(self.list_drifted_features()),
            },
        }
