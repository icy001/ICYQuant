"""Offline Feature Store — historical feature data for training and backtesting.

Provides time-range queries over historical feature data stored
in Parquet files or object storage. Designed for batch training
workloads at PB scale.

Usage::

    from services.feature_store import OfflineFeatureStore, OfflineQuery

    store = OfflineFeatureStore()
    store.write("ema20", "2024-01", df_data)
    data = store.read("ema20", start="2024-01-01", end="2024-01-31")
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PartitionUnit(str, Enum):
    """Time-based partition granularity."""

    YEAR = "year"
    MONTH = "month"
    DAY = "day"
    HOUR = "hour"


@dataclass
class OfflineQuery:
    """A query against the offline feature store.

    Attributes:
        feature_names: Feature names to retrieve.
        entity_ids: Optional entity ID filter (e.g. symbols).
        start_time: Start of time range (inclusive), Unix timestamp.
        end_time: End of time range (exclusive), Unix timestamp.
        columns: Specific columns to return (None = all).
        limit: Maximum rows to return.
        metadata_filter: Optional key-value filter on metadata.
    """

    feature_names: List[str]
    entity_ids: Optional[List[str]] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    columns: Optional[List[str]] = None
    limit: int = 100000
    metadata_filter: Optional[Dict[str, str]] = None


@dataclass
class OfflineDataset:
    """Metadata for an offline feature dataset.

    Attributes:
        feature_name: Feature name.
        partition_key: Partition identifier (e.g. "2024-01").
        partition_unit: Granularity of the partition.
        row_count: Number of rows in this partition.
        size_bytes: Approximate size in bytes.
        schema: Column name -> dtype mapping.
        created_at: Unix timestamp.
        metadata: Arbitrary metadata.
    """

    feature_name: str
    partition_key: str
    partition_unit: PartitionUnit = PartitionUnit.MONTH
    row_count: int = 0
    size_bytes: int = 0
    schema: Dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, str] = field(default_factory=dict)


class OfflineFeatureStore:
    """Historical feature store for batch training and backtesting.

    Manages time-partitioned feature datasets. In production, the
    actual storage layer (Parquet, S3) is provided by the
    infrastructure layer; this service layer provides the
    logical API and metadata management.

    Data is organized as:
        feature_name / partition_key / data
    """

    # ---- 分组：初始化 ----

    def __init__(self, base_path: str = "data/features/offline") -> None:
        """Initialize the offline store.

        Args:
            base_path: Root directory for offline feature data.
        """
        self.base_path = base_path
        self._datasets: Dict[str, Dict[str, OfflineDataset]] = {}  # feature_name -> partition_key -> dataset
        # In-memory data storage (backed by real storage in production)
        self._data: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}  # feature_name -> partition_key -> rows

    # ---- 分组：写入 ----

    def write(
        self,
        feature_name: str,
        partition_key: str,
        rows: List[Dict[str, Any]],
        partition_unit: PartitionUnit = PartitionUnit.MONTH,
        schema: Optional[Dict[str, str]] = None,
    ) -> OfflineDataset:
        """Write feature data to a partition.

        Args:
            feature_name: Feature name.
            partition_key: Partition identifier (e.g. "2024-01").
            rows: List of row dicts.
            partition_unit: Time granularity.
            schema: Optional column type mapping.

        Returns:
            OfflineDataset metadata.
        """
        self._datasets.setdefault(feature_name, {})
        self._data.setdefault(feature_name, {})

        # Infer schema if not provided
        if schema is None and rows:
            schema = {}
            for row in rows:
                for col, val in row.items():
                    if col not in schema:
                        schema[col] = type(val).__name__

        dataset = OfflineDataset(
            feature_name=feature_name,
            partition_key=partition_key,
            partition_unit=partition_unit,
            row_count=len(rows),
            size_bytes=len(str(rows)) if rows else 0,  # approximate
            schema=schema or {},
        )

        self._datasets[feature_name][partition_key] = dataset
        self._data[feature_name][partition_key] = rows
        return dataset

    def append(
        self,
        feature_name: str,
        partition_key: str,
        rows: List[Dict[str, Any]],
    ) -> Optional[OfflineDataset]:
        """Append rows to an existing partition.

        Args:
            feature_name: Feature name.
            partition_key: Partition identifier.
            rows: Rows to append.

        Returns:
            Updated OfflineDataset, or None if partition doesn't exist.
        """
        if feature_name not in self._data or partition_key not in self._data[feature_name]:
            return None

        self._data[feature_name][partition_key].extend(rows)
        dataset = self._datasets[feature_name][partition_key]
        dataset.row_count = len(self._data[feature_name][partition_key])
        dataset.size_bytes = len(str(self._data[feature_name][partition_key]))
        return dataset

    # ---- 分组：读取 ----

    def read(
        self,
        feature_name: str,
        partition_key: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        entity_ids: Optional[List[str]] = None,
        columns: Optional[List[str]] = None,
        limit: int = 100000,
    ) -> List[Dict[str, Any]]:
        """Read feature data with optional filters.

        Args:
            feature_name: Feature name.
            partition_key: Specific partition to read (if None, read all).
            start_time: Start of time range (timestamp column).
            end_time: End of time range (timestamp column).
            entity_ids: Entity ID filter (entity_id column).
            columns: Columns to return.
            limit: Max rows to return.

        Returns:
            List of row dicts.
        """
        if feature_name not in self._data:
            return []

        partitions = (
            [partition_key] if partition_key
            else sorted(self._data[feature_name].keys())
        )

        results: List[Dict[str, Any]] = []
        for pk in partitions:
            if pk not in self._data[feature_name]:
                continue
            for row in self._data[feature_name][pk]:
                # Time filter
                if start_time is not None:
                    ts = row.get("timestamp", row.get("time", 0))
                    if ts < start_time:
                        continue
                if end_time is not None:
                    ts = row.get("timestamp", row.get("time", 0))
                    if ts >= end_time:
                        continue
                # Entity filter
                if entity_ids is not None:
                    eid = row.get("entity_id", row.get("symbol", ""))
                    if eid not in entity_ids:
                        continue
                # Column filter
                if columns is not None:
                    row = {c: row[c] for c in columns if c in row}
                results.append(row)
                if len(results) >= limit:
                    return results

        return results

    def read_partition(
        self, feature_name: str, partition_key: str
    ) -> List[Dict[str, Any]]:
        """Read all data from a specific partition.

        Args:
            feature_name: Feature name.
            partition_key: Partition identifier.

        Returns:
            List of row dicts.
        """
        return list(self._data.get(feature_name, {}).get(partition_key, []))

    # ---- 分组：查询 ----

    def list_features(self) -> List[str]:
        """List all feature names in the store.

        Returns:
            Sorted list of feature names.
        """
        return sorted(self._data.keys())

    def list_partitions(self, feature_name: str) -> List[str]:
        """List partitions for a feature, sorted.

        Args:
            feature_name: Feature name.

        Returns:
            Sorted list of partition keys.
        """
        return sorted(self._data.get(feature_name, {}).keys())

    def get_dataset(self, feature_name: str, partition_key: str) -> Optional[OfflineDataset]:
        """Get dataset metadata for a partition.

        Args:
            feature_name: Feature name.
            partition_key: Partition identifier.

        Returns:
            OfflineDataset or None.
        """
        return self._datasets.get(feature_name, {}).get(partition_key)

    def get_schema(self, feature_name: str) -> Dict[str, str]:
        """Get the unified schema for a feature across all partitions.

        Args:
            feature_name: Feature name.

        Returns:
            Merged column -> dtype mapping.
        """
        schema: Dict[str, str] = {}
        for dataset in self._datasets.get(feature_name, {}).values():
            schema.update(dataset.schema)
        return schema

    # ---- 分组：管理 ----

    def delete_partition(self, feature_name: str, partition_key: str) -> bool:
        """Delete a partition.

        Args:
            feature_name: Feature name.
            partition_key: Partition identifier.

        Returns:
            True if deleted.
        """
        deleted = False
        if feature_name in self._data:
            self._data[feature_name].pop(partition_key, None)
            deleted = True
        if feature_name in self._datasets:
            self._datasets[feature_name].pop(partition_key, None)
        return deleted

    def delete_feature(self, feature_name: str) -> bool:
        """Delete an entire feature and all its partitions.

        Args:
            feature_name: Feature name.

        Returns:
            True if deleted.
        """
        deleted = bool(self._data.pop(feature_name, None))
        self._datasets.pop(feature_name, None)
        return deleted

    def total_rows(self, feature_name: Optional[str] = None) -> int:
        """Count total rows.

        Args:
            feature_name: Optional feature filter.

        Returns:
            Total row count.
        """
        if feature_name:
            return sum(len(rows) for rows in self._data.get(feature_name, {}).values())
        return sum(
            len(rows)
            for feature_data in self._data.values()
            for rows in feature_data.values()
        )

    def total_partitions(self) -> int:
        """Count total partitions across all features.

        Returns:
            Total partition count.
        """
        return sum(len(partitions) for partitions in self._data.values())
