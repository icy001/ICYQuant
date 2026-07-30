"""ICYQuant Partition Manager.

Manages data partitioning strategies for the lakehouse.
Supports:
    - Date-based partitioning (YYYY-MM-DD)
    - Hour-based partitioning
    - Symbol-based partitioning
    - Composite partitioning (symbol + date)
    - Automatic partition compaction
    - Schema evolution across partitions

Usage::

    pm = PartitionManager(PartitionConfig(), lakehouse)
    pm.create_partition("market_tick", "2026-07-29")
    pm.list_partitions("market_tick")
    pm.compact_partitions("market_tick", threshold_mb=128)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from services.data_platform.config import (
    PartitionConfig,
    PartitionType,
)
from services.data_platform.lakehouse import DataLakehouse, DataFile


# ============================================================================
# Partition Types
# ============================================================================


@dataclass
class PartitionInfo:
    """Metadata about a single partition."""

    partition_key: str
    dataset: str
    partition_type: PartitionType
    file_count: int = 0
    row_count: int = 0
    size_bytes: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    is_compacted: bool = False
    schema_version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "partition_key": self.partition_key,
            "dataset": self.dataset,
            "partition_type": self.partition_type.value,
            "file_count": self.file_count,
            "row_count": self.row_count,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "is_compacted": self.is_compacted,
            "schema_version": self.schema_version,
            "metadata": self.metadata,
        }


@dataclass
class PartitionSpec:
    """Specification for creating a partition."""

    partition_key: str
    partition_type: PartitionType = PartitionType.DATE
    min_value: Optional[str] = None
    max_value: Optional[str] = None
    location: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompactionResult:
    """Result of a partition compaction operation."""

    dataset: str
    partitions_compacted: int
    files_before: int
    files_after: int
    size_before_bytes: int
    size_after_bytes: int
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset,
            "partitions_compacted": self.partitions_compacted,
            "files_before": self.files_before,
            "files_after": self.files_after,
            "size_before_bytes": self.size_before_bytes,
            "size_after_bytes": self.size_after_bytes,
            "size_reduction_pct": round(
                (1 - self.size_after_bytes / max(self.size_before_bytes, 1)) * 100, 1
            ),
            "duration_ms": self.duration_ms,
        }


# ============================================================================
# Partition Manager
# ============================================================================


class PartitionManager:
    """Data Partition Manager.

    Manages data partitioning for efficient storage and query performance.

    Usage::

        pm = PartitionManager(PartitionConfig(), lakehouse)
        pm.create_partition("market_tick", "2026-07-29")
        pm.list_partitions("market_tick")
        result = pm.compact_partitions("market_tick")
    """

    def __init__(
        self,
        config: Optional[PartitionConfig] = None,
        lakehouse: Optional[DataLakehouse] = None,
    ) -> None:
        self.config = config or PartitionConfig()
        self.lakehouse = lakehouse
        self._partitions: Dict[str, Dict[str, PartitionInfo]] = {}
        self._partition_specs: Dict[str, PartitionSpec] = {}

    # ------------------------------------------------------------------
    # Partition Creation
    # ------------------------------------------------------------------

    def create_partition(
        self,
        dataset: str,
        partition_key: str,
        partition_type: Optional[PartitionType] = None,
        **kwargs: Any,
    ) -> PartitionInfo:
        """Create a new partition for a dataset.

        Args:
            dataset: Dataset name.
            partition_key: Partition key (e.g. "2026-07-29" or "AAPL").
            partition_type: Partition type (defaults to config default).
            **kwargs: Additional metadata.

        Returns:
            PartitionInfo for the new partition.
        """
        partition_type = partition_type or self.config.default_type

        info = PartitionInfo(
            partition_key=partition_key,
            dataset=dataset,
            partition_type=partition_type,
            metadata=kwargs,
        )

        self._partitions.setdefault(dataset, {})[partition_key] = info
        return info

    def get_partition(
        self, dataset: str, partition_key: str
    ) -> Optional[PartitionInfo]:
        """Get partition info by key."""
        return self._partitions.get(dataset, {}).get(partition_key)

    def list_partitions(
        self,
        dataset: str,
        partition_type: Optional[PartitionType] = None,
    ) -> List[PartitionInfo]:
        """List all partitions for a dataset.

        Args:
            dataset: Dataset name.
            partition_type: Filter by partition type.

        Returns:
            List of PartitionInfo.
        """
        partitions = list(self._partitions.get(dataset, {}).values())

        if partition_type:
            partitions = [p for p in partitions if p.partition_type == partition_type]

        # Sort by partition key
        partitions.sort(key=lambda p: p.partition_key)
        return partitions

    def get_partition_key(
        self,
        dataset: str,
        timestamp: Optional[datetime] = None,
        symbol: Optional[str] = None,
    ) -> str:
        """Generate a partition key from parameters.

        Args:
            dataset: Dataset name.
            timestamp: Timestamp for date/hour partitioning.
            symbol: Symbol for symbol-based partitioning.

        Returns:
            Partition key string.
        """
        spec = self._partition_specs.get(dataset)
        partition_type = spec.partition_type if spec else self.config.default_type

        ts = timestamp or datetime.utcnow()

        if partition_type == PartitionType.DATE:
            return ts.strftime("%Y-%m-%d")
        elif partition_type == PartitionType.HOUR:
            return ts.strftime("%Y-%m-%d-%H")
        elif partition_type == PartitionType.SYMBOL:
            return symbol or "default"
        elif partition_type == PartitionType.SYMBOL_DATE:
            sym = symbol or "default"
            return f"{sym}/{ts.strftime('%Y-%m-%d')}"
        else:
            return "default"

    # ------------------------------------------------------------------
    # Partition Spec
    # ------------------------------------------------------------------

    def set_partition_spec(self, dataset: str, spec: PartitionSpec) -> None:
        """Set the partition specification for a dataset.

        Args:
            dataset: Dataset name.
            spec: PartitionSpec.
        """
        self._partition_specs[dataset] = spec

    def get_partition_spec(self, dataset: str) -> Optional[PartitionSpec]:
        """Get the partition specification for a dataset."""
        return self._partition_specs.get(dataset)

    # ------------------------------------------------------------------
    # Data Operations
    # ------------------------------------------------------------------

    def write_to_partition(
        self,
        dataset: str,
        data: List[Dict[str, Any]],
        partition_key: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        symbol: Optional[str] = None,
    ) -> Optional[DataFile]:
        """Write data to the appropriate partition.

        Automatically creates the partition if it doesn't exist.

        Args:
            dataset: Dataset name.
            data: Data records.
            partition_key: Explicit partition key (auto-generated if None).
            timestamp: Timestamp for auto-generated key.
            symbol: Symbol for auto-generated key.

        Returns:
            DataFile metadata, or None if lakehouse not configured.
        """
        if partition_key is None:
            partition_key = self.get_partition_key(dataset, timestamp, symbol)

        # Ensure partition exists
        if dataset not in self._partitions or partition_key not in self._partitions.get(dataset, {}):
            self.create_partition(dataset, partition_key)

        # Update partition stats
        info = self._partitions[dataset][partition_key]
        info.file_count += 1
        info.row_count += len(data)
        info.size_bytes += sum(
            len(str(r).encode("utf-8")) for r in data
        )
        info.last_updated = datetime.utcnow()

        # Write to lakehouse
        if self.lakehouse:
            return self.lakehouse.write(
                dataset=dataset,
                data=data,
                partition=partition_key,
            )

        return None

    def read_partition(
        self,
        dataset: str,
        partition_key: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Read data from a specific partition.

        Args:
            dataset: Dataset name.
            partition_key: Partition key.
            limit: Maximum records.

        Returns:
            List of data records.
        """
        if self.lakehouse:
            return self.lakehouse.read(
                dataset=dataset,
                partition=partition_key,
                limit=limit,
            )
        return []

    # ------------------------------------------------------------------
    # Compaction
    # ------------------------------------------------------------------

    def compact_partitions(
        self,
        dataset: str,
        threshold_mb: Optional[int] = None,
    ) -> CompactionResult:
        """Compact small partitions into larger ones.

        Merges partitions below the threshold size for better query
        performance and reduced metadata overhead.

        Args:
            dataset: Dataset name.
            threshold_mb: Min partition size in MB before compaction.

        Returns:
            CompactionResult.
        """
        start = datetime.utcnow()
        threshold = threshold_mb or self.config.compaction_threshold_mb
        threshold_bytes = threshold * 1024 * 1024

        partitions = self.list_partitions(dataset)
        if not partitions:
            return CompactionResult(
                dataset=dataset,
                partitions_compacted=0,
                files_before=0,
                files_after=0,
                size_before_bytes=0,
                size_after_bytes=0,
            )

        # Find small partitions
        small = [p for p in partitions if p.size_bytes < threshold_bytes]
        large = [p for p in partitions if p.size_bytes >= threshold_bytes]

        files_before = sum(p.file_count for p in partitions)
        size_before = sum(p.size_bytes for p in partitions)

        compacted = 0
        if len(small) >= 2:
            # Merge all small partitions into one
            merged_key = small[0].partition_key
            merged_info = small[0]
            merged_info.is_compacted = True

            for p in small[1:]:
                merged_info.row_count += p.row_count
                merged_info.size_bytes += p.size_bytes
                merged_info.file_count += p.file_count
                # Remove old partition
                del self._partitions[dataset][p.partition_key]
                compacted += 1

        files_after = sum(
            p.file_count for p in self._partitions.get(dataset, {}).values()
        )
        size_after = sum(
            p.size_bytes for p in self._partitions.get(dataset, {}).values()
        )

        duration = (datetime.utcnow() - start).total_seconds() * 1000

        return CompactionResult(
            dataset=dataset,
            partitions_compacted=compacted,
            files_before=files_before,
            files_after=files_after,
            size_before_bytes=size_before,
            size_after_bytes=size_after,
            duration_ms=duration,
        )

    # ------------------------------------------------------------------
    # Schema Evolution Across Partitions
    # ------------------------------------------------------------------

    def evolve_partition_schema(
        self,
        dataset: str,
        partition_key: str,
        new_schema_version: int,
        added_columns: Optional[List[Dict[str, Any]]] = None,
        removed_columns: Optional[List[str]] = None,
    ) -> bool:
        """Evolve the schema for a specific partition.

        Supports adding new columns to old partitions without data
        migration — new columns get NULL for existing rows.

        Args:
            dataset: Dataset name.
            partition_key: Partition key.
            new_schema_version: New schema version number.
            added_columns: List of new column definitions.
            removed_columns: List of columns to remove.

        Returns:
            True if evolution was successful.
        """
        info = self.get_partition(dataset, partition_key)
        if not info:
            return False

        info.schema_version = new_schema_version

        if added_columns:
            info.metadata.setdefault("added_columns", []).extend(added_columns)

        if removed_columns:
            info.metadata.setdefault("removed_columns", []).extend(removed_columns)

        return True

    def get_partition_schema_versions(
        self, dataset: str
    ) -> Dict[str, int]:
        """Get schema versions across all partitions.

        Args:
            dataset: Dataset name.

        Returns:
            Dict mapping partition_key → schema_version.
        """
        return {
            key: info.schema_version
            for key, info in self._partitions.get(dataset, {}).items()
        }

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Get partition management statistics."""
        total_partitions = sum(
            len(partitions) for partitions in self._partitions.values()
        )
        total_datasets = len(self._partitions)

        by_type: Dict[str, int] = {}
        for partitions in self._partitions.values():
            for info in partitions.values():
                by_type[info.partition_type.value] = (
                    by_type.get(info.partition_type.value, 0) + 1
                )

        return {
            "total_datasets": total_datasets,
            "total_partitions": total_partitions,
            "by_type": by_type,
            "compacted_partitions": sum(
                1 for partitions in self._partitions.values()
                for info in partitions.values()
                if info.is_compacted
            ),
        }
