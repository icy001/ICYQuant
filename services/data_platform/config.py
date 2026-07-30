"""Data Platform configuration module.

Defines all configuration dataclasses and enums for the institutional
data lakehouse and quant data fabric.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ============================================================================
# Enums
# ============================================================================


class StorageTier(str, Enum):
    """Data storage tier for lifecycle management."""

    HOT = "hot"          # High-frequency access (SSD / in-memory)
    WARM = "warm"        # Moderate access (HDD / cloud storage)
    COLD = "cold"        # Archive (object storage / tape)


class DataClassification(str, Enum):
    """Data sensitivity classification."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class QualityRuleType(str, Enum):
    """Types of data quality rules."""

    NOT_NULL = "not_null"
    UNIQUE = "unique"
    RANGE = "range"
    ENUM = "enum"
    REGEX = "regex"
    CUSTOM = "custom"
    TIMELINESS = "timeliness"
    REFERENTIAL = "referential"


class AccessLevel(str, Enum):
    """Data access permission levels."""

    NONE = "none"
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


class SchemaCompatibility(str, Enum):
    """Schema evolution compatibility modes."""

    BACKWARD = "backward"          # New schema can read old data
    FORWARD = "forward"            # Old schema can read new data
    FULL = "full"                  # Both backward and forward
    NONE = "none"                  # No compatibility guaranteed


class PartitionType(str, Enum):
    """Data partition strategies."""

    DATE = "date"                  # Partition by date (YYYY-MM-DD)
    HOUR = "hour"                  # Partition by hour
    SYMBOL = "symbol"              # Partition by symbol/ticker
    SYMBOL_DATE = "symbol_date"    # Partition by symbol + date
    NONE = "none"                  # No partitioning


class LifecycleAction(str, Enum):
    """Actions in data lifecycle policy."""

    KEEP = "keep"
    COMPRESS = "compress"
    ARCHIVE = "archive"
    DELETE = "delete"


class SnapshotFrequency(str, Enum):
    """Snapshot creation frequency."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    MANUAL = "manual"


class CatalogEntryType(str, Enum):
    """Types of entries in the metadata catalog."""

    DATASET = "dataset"
    TABLE = "table"
    VIEW = "view"
    FEATURE = "feature"
    MODEL = "model"
    PIPELINE = "pipeline"
    REPORT = "report"


# ============================================================================
# Configuration Dataclasses
# ============================================================================


@dataclass
class LakehouseConfig:
    """Data lakehouse configuration.

    Attributes:
        name: Lakehouse instance name.
        base_path: Root storage path.
        default_tier: Default storage tier for new data.
        enable_time_travel: Enable time-travel queries.
        time_travel_retention_days: How long to keep historical snapshots.
        max_open_snapshots: Maximum concurrent snapshots.
    """

    name: str = "icyquant_lakehouse"
    base_path: str = "data/lakehouse"
    default_tier: StorageTier = StorageTier.HOT
    enable_time_travel: bool = True
    time_travel_retention_days: int = 30
    max_open_snapshots: int = 100
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class CatalogConfig:
    """Metadata catalog configuration.

    Attributes:
        enable_search: Enable full-text search on metadata.
        enable_lineage: Enable automatic lineage tracking.
        cache_ttl_seconds: Metadata cache TTL.
        max_tags_per_entry: Maximum tags per catalog entry.
    """

    enable_search: bool = True
    enable_lineage: bool = True
    cache_ttl_seconds: int = 300
    max_tags_per_entry: int = 20
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class SchemaRegistryConfig:
    """Schema registry configuration.

    Attributes:
        compatibility_mode: Default compatibility mode.
        validate_on_write: Validate data against schema on write.
        max_versions: Maximum schema versions to retain.
        allow_field_addition: Allow adding new optional fields.
    """

    compatibility_mode: SchemaCompatibility = SchemaCompatibility.BACKWARD
    validate_on_write: bool = True
    max_versions: int = 100
    allow_field_addition: bool = True
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class LineageConfig:
    """Data lineage configuration.

    Attributes:
        track_transforms: Track data transformations.
        track_queries: Track query lineage.
        max_depth: Maximum lineage depth to traverse.
        store_ttl_days: How long to retain lineage records.
    """

    track_transforms: bool = True
    track_queries: bool = True
    max_depth: int = 50
    store_ttl_days: int = 365
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class QualityConfig:
    """Data quality engine configuration.

    Attributes:
        validate_on_ingest: Run quality checks on data ingestion.
        validate_on_read: Run quality checks on data access.
        max_rules_per_dataset: Maximum rules per dataset.
        alert_threshold: Fraction of failed checks before alerting.
        store_results_days: How long to retain quality check results.
    """

    validate_on_ingest: bool = True
    validate_on_read: bool = False
    max_rules_per_dataset: int = 50
    alert_threshold: float = 0.1
    store_results_days: int = 90
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class GovernanceConfig:
    """Data governance configuration.

    Attributes:
        require_owner: Require data owner for all datasets.
        require_classification: Require data classification.
        audit_enabled: Enable audit logging.
        audit_retention_days: Audit log retention period.
        auto_classify: Auto-classify data based on rules.
    """

    require_owner: bool = True
    require_classification: bool = True
    audit_enabled: bool = True
    audit_retention_days: int = 365
    auto_classify: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class AccessControlConfig:
    """Access control configuration.

    Attributes:
        enforce_rbac: Enforce role-based access control.
        default_access: Default access level for new users.
        token_ttl_hours: Access token TTL in hours.
        max_roles_per_user: Maximum roles per user.
    """

    enforce_rbac: bool = True
    default_access: AccessLevel = AccessLevel.NONE
    token_ttl_hours: int = 24
    max_roles_per_user: int = 10
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class VersionConfig:
    """Data versioning configuration.

    Attributes:
        snapshot_frequency: Default snapshot frequency.
        max_snapshots: Maximum snapshots to retain.
        snapshot_retention_days: Days to retain snapshots.
        enable_auto_snapshot: Auto-create snapshots on schedule.
    """

    snapshot_frequency: SnapshotFrequency = SnapshotFrequency.DAILY
    max_snapshots: int = 365
    snapshot_retention_days: int = 90
    enable_auto_snapshot: bool = True
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class TimeTravelConfig:
    """Time travel configuration.

    Attributes:
        enabled: Enable time-travel queries.
        default_branch: Default branch name.
        max_history_days: Maximum days of history to retain.
        vacuum_interval_hours: Interval for cleaning old snapshots.
    """

    enabled: bool = True
    default_branch: str = "main"
    max_history_days: int = 30
    vacuum_interval_hours: int = 24
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class PartitionConfig:
    """Partition management configuration.

    Attributes:
        default_type: Default partition type.
        max_partitions: Maximum partitions per dataset.
        auto_compact: Auto-compact small partitions.
        compaction_threshold_mb: Min partition size before compaction.
    """

    default_type: PartitionType = PartitionType.DATE
    max_partitions: int = 10000
    auto_compact: bool = True
    compaction_threshold_mb: int = 128
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class LifecycleConfig:
    """Data lifecycle configuration.

    Attributes:
        default_policy: Default lifecycle policy name.
        enforce_retention: Enforce retention policies.
        hot_retention_days: Days to keep data in hot tier.
        warm_retention_days: Days to keep data in warm tier.
        cold_retention_days: Days to keep data in cold tier.
    """

    default_policy: str = "standard"
    enforce_retention: bool = True
    hot_retention_days: int = 30
    warm_retention_days: int = 90
    cold_retention_days: int = 365
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class DataPlatformConfig:
    """Master configuration for the institutional data platform.

    Attributes:
        lakehouse: Lakehouse configuration.
        catalog: Metadata catalog configuration.
        schema_registry: Schema registry configuration.
        lineage: Data lineage configuration.
        quality: Data quality configuration.
        governance: Governance configuration.
        access_control: Access control configuration.
        versioning: Version/snapshot configuration.
        time_travel: Time travel configuration.
        partition: Partition configuration.
        lifecycle: Lifecycle configuration.
    """

    lakehouse: LakehouseConfig = field(default_factory=LakehouseConfig)
    catalog: CatalogConfig = field(default_factory=CatalogConfig)
    schema_registry: SchemaRegistryConfig = field(default_factory=SchemaRegistryConfig)
    lineage: LineageConfig = field(default_factory=LineageConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    governance: GovernanceConfig = field(default_factory=GovernanceConfig)
    access_control: AccessControlConfig = field(default_factory=AccessControlConfig)
    versioning: VersionConfig = field(default_factory=VersionConfig)
    time_travel: TimeTravelConfig = field(default_factory=TimeTravelConfig)
    partition: PartitionConfig = field(default_factory=PartitionConfig)
    lifecycle: LifecycleConfig = field(default_factory=LifecycleConfig)
    metadata: Dict[str, str] = field(default_factory=dict)
