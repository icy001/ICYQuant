"""Parquet Store — columnar storage for offline feature data.

Provides efficient read/write of time-partitioned Parquet files
for PB-scale offline feature storage. Supports schema evolution,
compression, and predicate pushdown for fast time-range queries.

Usage::

    from infrastructure.storage import ParquetStore

    store = ParquetStore(base_path="data/features/offline")
    store.write("ema20", "2024-01", rows)
    data = store.read("ema20", partition_key="2024-01")
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CompressionCodec(str, Enum):
    """Supported compression codecs."""

    SNAPPY = "snappy"
    GZIP = "gzip"
    ZSTD = "zstd"
    LZ4 = "lz4"
    NONE = "none"


@dataclass
class ParquetPartition:
    """Metadata for a Parquet partition.

    Attributes:
        feature_name: Feature name.
        partition_key: Partition identifier.
        file_path: Relative file path.
        row_count: Number of rows.
        size_bytes: File size in bytes.
        compression: Compression codec used.
        schema_json: JSON-serialized schema.
        created_at: Unix timestamp.
    """

    feature_name: str
    partition_key: str
    file_path: str = ""
    row_count: int = 0
    size_bytes: int = 0
    compression: CompressionCodec = CompressionCodec.SNAPPY
    schema_json: str = "{}"
    created_at: float = field(default_factory=time.time)


class ParquetStore:
    """Columnar storage backend for offline feature data.

    Uses Parquet format for efficient storage and query of
    large-scale feature datasets. In production, delegates to
    pyarrow/pandas; the current implementation provides the
    logical API with in-memory backing for testing.
    """

    # ---- 分组：初始化 ----

    def __init__(
        self,
        base_path: str = "data/features/offline",
        compression: CompressionCodec = CompressionCodec.SNAPPY,
        row_group_size: int = 100000,
    ) -> None:
        """Initialize the Parquet store.

        Args:
            base_path: Root directory for Parquet files.
            compression: Default compression codec.
            row_group_size: Row group size for Parquet writing.
        """
        self.base_path = base_path
        self.compression = compression
        self.row_group_size = row_group_size
        self._partitions: Dict[str, Dict[str, ParquetPartition]] = {}
        self._data: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        self._ensure_base_path()

    def _ensure_base_path(self) -> None:
        """Ensure the base directory exists."""
        os.makedirs(self.base_path, exist_ok=True)

    # ---- 分组：写入 ----

    def write(
        self,
        feature_name: str,
        partition_key: str,
        rows: List[Dict[str, Any]],
        compression: Optional[CompressionCodec] = None,
    ) -> ParquetPartition:
        """Write rows to a Parquet partition.

        Args:
            feature_name: Feature name.
            partition_key: Partition identifier.
            rows: Data rows as list of dicts.
            compression: Optional compression override.

        Returns:
            ParquetPartition metadata.
        """
        codec = compression or self.compression

        # Build file path
        feature_dir = os.path.join(self.base_path, feature_name)
        os.makedirs(feature_dir, exist_ok=True)
        file_name = f"{partition_key}.parquet"
        file_path = os.path.join(feature_dir, file_name)

        # Extract schema
        schema: Dict[str, str] = {}
        if rows:
            for row in rows:
                for col, val in row.items():
                    if col not in schema:
                        schema[col] = type(val).__name__

        # In-memory backing
        self._data.setdefault(feature_name, {})
        self._data[feature_name][partition_key] = rows

        partition = ParquetPartition(
            feature_name=feature_name,
            partition_key=partition_key,
            file_path=file_path,
            row_count=len(rows),
            size_bytes=len(json.dumps(rows, default=str)),
            compression=codec,
            schema_json=json.dumps(schema),
        )

        self._partitions.setdefault(feature_name, {})
        self._partitions[feature_name][partition_key] = partition
        return partition

    def append(
        self,
        feature_name: str,
        partition_key: str,
        rows: List[Dict[str, Any]],
    ) -> Optional[ParquetPartition]:
        """Append rows to an existing partition.

        Args:
            feature_name: Feature name.
            partition_key: Partition identifier.
            rows: Rows to append.

        Returns:
            Updated ParquetPartition, or None if partition doesn't exist.
        """
        if feature_name not in self._data or partition_key not in self._data[feature_name]:
            return None

        self._data[feature_name][partition_key].extend(rows)
        partition = self._partitions[feature_name][partition_key]
        partition.row_count = len(self._data[feature_name][partition_key])
        partition.size_bytes = len(json.dumps(self._data[feature_name][partition_key], default=str))
        return partition

    # ---- 分组：读取 ----

    def read(
        self,
        feature_name: str,
        partition_key: Optional[str] = None,
        columns: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100000,
    ) -> List[Dict[str, Any]]:
        """Read data from Parquet partitions.

        Args:
            feature_name: Feature name.
            partition_key: Specific partition or None for all.
            columns: Columns to return (None = all).
            filters: Column -> value equality filters.
            limit: Maximum rows.

        Returns:
            List of row dicts.
        """
        if feature_name not in self._data:
            return []

        partition_keys = (
            [partition_key] if partition_key
            else sorted(self._data[feature_name].keys())
        )

        results: List[Dict[str, Any]] = []
        for pk in partition_keys:
            if pk not in self._data[feature_name]:
                continue
            for row in self._data[feature_name][pk]:
                # Apply filters
                if filters:
                    skip = False
                    for col, val in filters.items():
                        if row.get(col) != val:
                            skip = True
                            break
                    if skip:
                        continue
                # Column projection
                if columns is not None:
                    row = {c: row[c] for c in columns if c in row}
                results.append(row)
                if len(results) >= limit:
                    return results

        return results

    def read_partition(
        self, feature_name: str, partition_key: str
    ) -> List[Dict[str, Any]]:
        """Read all rows from a single partition.

        Args:
            feature_name: Feature name.
            partition_key: Partition identifier.

        Returns:
            List of row dicts.
        """
        return list(self._data.get(feature_name, {}).get(partition_key, []))

    # ---- 分组：查询 ----

    def get_partition(self, feature_name: str, partition_key: str) -> Optional[ParquetPartition]:
        """Get partition metadata.

        Args:
            feature_name: Feature name.
            partition_key: Partition identifier.

        Returns:
            ParquetPartition or None.
        """
        return self._partitions.get(feature_name, {}).get(partition_key)

    def list_features(self) -> List[str]:
        """List all features stored.

        Returns:
            Sorted feature names.
        """
        return sorted(self._data.keys())

    def list_partitions(self, feature_name: str) -> List[ParquetPartition]:
        """List all partitions for a feature, sorted by key.

        Args:
            feature_name: Feature name.

        Returns:
            List of ParquetPartition.
        """
        partitions = list(self._partitions.get(feature_name, {}).values())
        partitions.sort(key=lambda p: p.partition_key)
        return partitions

    def get_schema(self, feature_name: str) -> Dict[str, str]:
        """Get unified schema across all partitions.

        Args:
            feature_name: Feature name.

        Returns:
            Merged column -> dtype dict.
        """
        schema: Dict[str, str] = {}
        for p in self._partitions.get(feature_name, {}).values():
            try:
                p_schema = json.loads(p.schema_json)
                schema.update(p_schema)
            except json.JSONDecodeError:
                pass
        return schema

    def row_count(self, feature_name: Optional[str] = None) -> int:
        """Total row count, optionally filtered by feature.

        Args:
            feature_name: Optional feature filter.

        Returns:
            Row count.
        """
        if feature_name:
            return sum(len(rows) for rows in self._data.get(feature_name, {}).values())
        return sum(
            len(rows)
            for feature_data in self._data.values()
            for rows in feature_data.values()
        )

    def partition_count(self) -> int:
        """Total partition count across all features.

        Returns:
            Partition count.
        """
        return sum(len(partitions) for partitions in self._data.values())

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
        if feature_name in self._partitions:
            self._partitions[feature_name].pop(partition_key, None)
        return deleted

    def delete_feature(self, feature_name: str) -> bool:
        """Delete an entire feature and all partitions.

        Args:
            feature_name: Feature name.

        Returns:
            True if deleted.
        """
        deleted = bool(self._data.pop(feature_name, None))
        self._partitions.pop(feature_name, None)
        return deleted

    def compact(self, feature_name: str) -> int:
        """Compact all partitions for a feature into a single partition.

        Args:
            feature_name: Feature name.

        Returns:
            Number of partitions compacted.
        """
        if feature_name not in self._data:
            return 0

        all_rows: List[Dict[str, Any]] = []
        for pk in sorted(self._data[feature_name].keys()):
            all_rows.extend(self._data[feature_name][pk])

        partition_count = len(self._data[feature_name])
        self._data[feature_name].clear()
        self._partitions[feature_name].clear()

        if all_rows:
            self.write(feature_name, "compacted", all_rows)

        return partition_count
