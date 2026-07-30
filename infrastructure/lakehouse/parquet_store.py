"""ICYQuant Parquet Store.

High-performance Parquet file storage for the lakehouse.
Supports columnar reads, predicate pushdown, and compression.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ParquetFileMetadata:
    """Metadata for a stored Parquet file."""

    file_id: str
    path: str
    dataset: str
    partition: str
    row_count: int
    size_bytes: int
    columns: List[str] = field(default_factory=list)
    compression: str = "snappy"
    created_at: datetime = field(default_factory=datetime.utcnow)
    row_groups: int = 1
    min_values: Dict[str, Any] = field(default_factory=dict)
    max_values: Dict[str, Any] = field(default_factory=dict)
    null_counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_id": self.file_id,
            "path": self.path,
            "dataset": self.dataset,
            "partition": self.partition,
            "row_count": self.row_count,
            "size_bytes": self.size_bytes,
            "columns": self.columns,
            "compression": self.compression,
            "created_at": self.created_at.isoformat(),
            "row_groups": self.row_groups,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ParquetFileMetadata":
        return cls(
            file_id=d["file_id"],
            path=d["path"],
            dataset=d["dataset"],
            partition=d["partition"],
            row_count=d["row_count"],
            size_bytes=d["size_bytes"],
            columns=d.get("columns", []),
            compression=d.get("compression", "snappy"),
            created_at=datetime.fromisoformat(d["created_at"]) if "created_at" in d else datetime.utcnow(),
            row_groups=d.get("row_groups", 1),
        )


@dataclass
class Predicate:
    """Push-down predicate for columnar reads."""

    column: str
    op: str  # eq, ne, lt, gt, lte, gte, in, between, is_null
    value: Any = None
    value2: Any = None  # For 'between'

    def evaluate(self, row: Dict[str, Any]) -> bool:
        """Evaluate this predicate against a row."""
        val = row.get(self.column)
        if val is None:
            return self.op == "is_null"

        if self.op == "eq":
            return val == self.value
        elif self.op == "ne":
            return val != self.value
        elif self.op == "lt":
            return val < self.value
        elif self.op == "gt":
            return val > self.value
        elif self.op == "lte":
            return val <= self.value
        elif self.op == "gte":
            return val >= self.value
        elif self.op == "in":
            return val in (self.value or [])
        elif self.op == "between":
            return self.value <= val <= self.value2
        elif self.op == "is_null":
            return val is None

        return True


class ParquetStore:
    """High-performance Parquet file storage.

    Simulates Parquet columnar storage with predicate pushdown,
    compression metadata, and row group statistics.

    In production, this would integrate with PyArrow/Parquet libraries.

    Usage::

        store = ParquetStore(base_path="data/lakehouse")
        meta = store.write("market_tick", "2026-07-29", data)
        filtered = store.read("market_tick", predicates=[Predicate("volume", "gt", 0)])
    """

    def __init__(self, base_path: str = "data/lakehouse") -> None:
        self.base_path = base_path
        self._files: Dict[str, ParquetFileMetadata] = {}
        self._data_cache: Dict[str, List[Dict[str, Any]]] = {}
        os.makedirs(base_path, exist_ok=True)
        self._load_index()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write(
        self,
        dataset: str,
        partition: str,
        data: List[Dict[str, Any]],
        compression: str = "snappy",
    ) -> ParquetFileMetadata:
        """Write data as a Parquet file.

        Args:
            dataset: Dataset name.
            partition: Partition key.
            data: Records to write.
            compression: Compression codec.

        Returns:
            ParquetFileMetadata.
        """
        file_id = str(uuid.uuid4())
        partition_dir = os.path.join(self.base_path, dataset, partition)
        os.makedirs(partition_dir, exist_ok=True)

        file_path = os.path.join(partition_dir, f"{file_id}.parquet")

        # Compute column statistics
        columns = list(data[0].keys()) if data else []
        min_values: Dict[str, Any] = {}
        max_values: Dict[str, Any] = {}
        null_counts: Dict[str, int] = {}

        for col in columns:
            values = [r.get(col) for r in data if r.get(col) is not None]
            if values:
                try:
                    min_values[col] = min(values)
                    max_values[col] = max(values)
                except TypeError:
                    pass
            null_counts[col] = sum(1 for r in data if r.get(col) is None)

        # Simulate compression (estimate ~50% for numeric data)
        raw_size = len(json.dumps(data).encode("utf-8"))
        compressed_size = int(raw_size * 0.5) if compression != "none" else raw_size

        meta = ParquetFileMetadata(
            file_id=file_id,
            path=file_path,
            dataset=dataset,
            partition=partition,
            row_count=len(data),
            size_bytes=compressed_size,
            columns=columns,
            compression=compression,
            row_groups=max(1, len(data) // 10000),
            min_values=min_values,
            max_values=max_values,
            null_counts=null_counts,
        )

        self._files[file_id] = meta
        self._data_cache[file_id] = data
        self._save_index()
        return meta

    # ------------------------------------------------------------------
    # Read with Predicate Pushdown
    # ------------------------------------------------------------------

    def read(
        self,
        dataset: str,
        partition: Optional[str] = None,
        columns: Optional[List[str]] = None,
        predicates: Optional[List[Predicate]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Read data with predicate pushdown.

        Filters are applied at the column level to minimize I/O.

        Args:
            dataset: Dataset name.
            partition: Partition filter.
            columns: Column projection.
            predicates: Push-down predicates.
            limit: Row limit.

        Returns:
            Filtered data records.
        """
        results: List[Dict[str, Any]] = []

        for file_id, meta in self._files.items():
            if meta.dataset != dataset:
                continue
            if partition and meta.partition != partition:
                continue

            # Check if predicates can be satisfied using min/max stats
            if predicates:
                if not self._can_match(meta, predicates):
                    continue  # Skip entire file

            # Read data
            data = self._data_cache.get(file_id, [])

            # Apply predicates
            if predicates:
                for pred in predicates:
                    data = [r for r in data if pred.evaluate(r)]

            results.extend(data)

            if limit and len(results) >= limit:
                break

        # Column projection
        if columns and results:
            results = [
                {c: r.get(c) for c in columns if c in r}
                for r in results
            ]

        if limit:
            results = results[:limit]

        return results

    def _can_match(self, meta: ParquetFileMetadata, predicates: List[Predicate]) -> bool:
        """Check if a file's min/max stats can satisfy predicates."""
        for pred in predicates:
            col_min = meta.min_values.get(pred.column)
            col_max = meta.max_values.get(pred.column)

            if col_min is None or col_max is None:
                continue

            if pred.op == "eq" and pred.value is not None:
                if pred.value < col_min or pred.value > col_max:
                    return False
            elif pred.op == "lt" and pred.value is not None:
                if col_min >= pred.value:
                    return False
            elif pred.op == "gt" and pred.value is not None:
                if col_max <= pred.value:
                    return False

        return True

    # ------------------------------------------------------------------
    # Management
    # ------------------------------------------------------------------

    def get_metadata(self, file_id: str) -> Optional[ParquetFileMetadata]:
        """Get file metadata."""
        return self._files.get(file_id)

    def list_files(
        self,
        dataset: Optional[str] = None,
        partition: Optional[str] = None,
    ) -> List[ParquetFileMetadata]:
        """List files with optional filters."""
        results = list(self._files.values())
        if dataset:
            results = [f for f in results if f.dataset == dataset]
        if partition:
            results = [f for f in results if f.partition == partition]
        return results

    def delete_file(self, file_id: str) -> bool:
        """Delete a file and its data."""
        if file_id in self._files:
            del self._files[file_id]
            self._data_cache.pop(file_id, None)
            self._save_index()
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        datasets: Dict[str, Dict[str, Any]] = {}

        for meta in self._files.values():
            if meta.dataset not in datasets:
                datasets[meta.dataset] = {"files": 0, "rows": 0, "size_bytes": 0, "partitions": set()}
            ds = datasets[meta.dataset]
            ds["files"] += 1
            ds["rows"] += meta.row_count
            ds["size_bytes"] += meta.size_bytes
            ds["partitions"].add(meta.partition)

        return {
            "total_files": len(self._files),
            "datasets": {
                ds: {
                    "files": info["files"],
                    "rows": info["rows"],
                    "size_bytes": info["size_bytes"],
                    "partitions": len(info["partitions"]),
                }
                for ds, info in datasets.items()
            },
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_index(self) -> None:
        index_path = os.path.join(self.base_path, "_parquet_index.json")
        if os.path.exists(index_path):
            try:
                with open(index_path, "r") as f:
                    state = json.load(f)
                for file_data in state.get("files", []):
                    meta = ParquetFileMetadata.from_dict(file_data)
                    self._files[meta.file_id] = meta
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_index(self) -> None:
        index_path = os.path.join(self.base_path, "_parquet_index.json")
        state = {
            "files": [m.to_dict() for m in self._files.values()],
            "updated_at": datetime.utcnow().isoformat(),
        }
        with open(index_path, "w") as f:
            json.dump(state, f, indent=2, default=str)
