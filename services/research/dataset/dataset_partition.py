"""Dataset Partition — partition management for large datasets.

Supports time-based, hash-based, and range-based partitioning
for efficient data access and parallel processing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class PartitionStrategy(str, Enum):
    """Partitioning strategies for datasets."""

    NONE = "none"
    TIME = "time"         # By date/time (year/month/day)
    HASH = "hash"         # By hash of key columns
    RANGE = "range"       # By value range
    LIST = "list"         # By explicit list of values
    COMPOSITE = "composite"  # Multi-level partitioning


@dataclass
class DatasetPartition:
    """Represents a single partition of a dataset.

    Partitions enable:
    * Efficient time-range queries
    * Parallel processing
    * Incremental updates
    * Data lifecycle management
    """

    id: str = ""
    dataset_id: str = ""
    partition_key: str = ""
    partition_value: str = ""
    strategy: PartitionStrategy = PartitionStrategy.NONE
    row_count: int = 0
    size_bytes: int = 0
    storage_path: str = ""
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "dataset_id": self.dataset_id,
            "partition_key": self.partition_key,
            "partition_value": self.partition_value,
            "strategy": self.strategy.value,
            "row_count": self.row_count,
            "size_bytes": self.size_bytes,
            "storage_path": self.storage_path,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"DatasetPartition(dataset={self.dataset_id[:8]}, "
            f"key={self.partition_key}={self.partition_value})"
        )


class PartitionManager:
    """Manages dataset partitions for efficient data access."""

    def __init__(self) -> None:
        self._partitions: Dict[str, List[DatasetPartition]] = {}

    def add_partition(self, partition: DatasetPartition) -> None:
        self._partitions.setdefault(partition.dataset_id, []).append(partition)

    def get_partitions(self, dataset_id: str) -> List[DatasetPartition]:
        return self._partitions.get(dataset_id, [])

    def get_partition(self, dataset_id: str, partition_key: str) -> Optional[DatasetPartition]:
        for p in self.get_partitions(dataset_id):
            if p.partition_key == partition_key:
                return p
        return None

    def remove_partition(self, dataset_id: str, partition_key: str) -> bool:
        partitions = self._partitions.get(dataset_id, [])
        before = len(partitions)
        self._partitions[dataset_id] = [
            p for p in partitions if p.partition_key != partition_key
        ]
        return len(self._partitions.get(dataset_id, [])) < before

    def total_row_count(self, dataset_id: str) -> int:
        return sum(p.row_count for p in self.get_partitions(dataset_id))

    def partition_count(self, dataset_id: str) -> int:
        return len(self.get_partitions(dataset_id))

    def summary(self, dataset_id: str) -> Dict[str, Any]:
        partitions = self.get_partitions(dataset_id)
        return {
            "dataset_id": dataset_id,
            "partition_count": len(partitions),
            "total_rows": sum(p.row_count for p in partitions),
            "total_size_bytes": sum(p.size_bytes for p in partitions),
        }
