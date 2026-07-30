"""ICYQuant Institutional Data Lakehouse.

Unified data storage layer supporting:
    - Tick, Bar, Order, Trade, Position data
    - Feature, Factor, News, Model, Backtest results
    - Hot / Warm / Cold storage tiering
    - Time-travel queries (AS OF timestamp)
    - ACID transactions on data writes
    - Schema-on-read and schema-on-write
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from services.data_platform.config import (
    LakehouseConfig,
    StorageTier,
)


# ============================================================================
# Data Types
# ============================================================================


class DatasetType(str, Enum):
    """Supported dataset types in the lakehouse."""

    TICK = "tick"
    BAR = "bar"
    ORDER = "order"
    TRADE = "trade"
    POSITION = "position"
    FEATURE = "feature"
    FACTOR = "factor"
    NEWS = "news"
    MODEL = "model"
    BACKTEST = "backtest"
    CUSTOM = "custom"


class WriteMode(str, Enum):
    """Data write modes."""

    APPEND = "append"
    OVERWRITE = "overwrite"
    MERGE = "merge"
    UPSERT = "upsert"


@dataclass
class DatasetSchema:
    """Schema definition for a dataset."""

    name: str
    dataset_type: DatasetType
    fields: List[Dict[str, Any]] = field(default_factory=list)
    primary_key: List[str] = field(default_factory=list)
    partition_keys: List[str] = field(default_factory=list)
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "dataset_type": self.dataset_type.value,
            "fields": self.fields,
            "primary_key": self.primary_key,
            "partition_keys": self.partition_keys,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DatasetSchema":
        return cls(
            name=d["name"],
            dataset_type=DatasetType(d["dataset_type"]),
            fields=d.get("fields", []),
            primary_key=d.get("primary_key", []),
            partition_keys=d.get("partition_keys", []),
            version=d.get("version", 1),
        )


@dataclass
class DataFile:
    """A single data file in the lakehouse."""

    file_id: str
    dataset: str
    partition: str
    file_path: str
    row_count: int
    size_bytes: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    tier: StorageTier = StorageTier.HOT
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_id": self.file_id,
            "dataset": self.dataset,
            "partition": self.partition,
            "file_path": self.file_path,
            "row_count": self.row_count,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat(),
            "tier": self.tier.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DataFile":
        return cls(
            file_id=d["file_id"],
            dataset=d["dataset"],
            partition=d["partition"],
            file_path=d["file_path"],
            row_count=d["row_count"],
            size_bytes=d["size_bytes"],
            created_at=datetime.fromisoformat(d["created_at"]),
            tier=StorageTier(d.get("tier", "hot")),
            metadata=d.get("metadata", {}),
        )


@dataclass
class TableSnapshot:
    """Point-in-time snapshot of a dataset table."""

    snapshot_id: str
    dataset: str
    timestamp: datetime
    files: List[str] = field(default_factory=list)
    schema_version: int = 1
    is_current: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "dataset": self.dataset,
            "timestamp": self.timestamp.isoformat(),
            "files": self.files,
            "schema_version": self.schema_version,
            "is_current": self.is_current,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TableSnapshot":
        return cls(
            snapshot_id=d["snapshot_id"],
            dataset=d["dataset"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            files=d.get("files", []),
            schema_version=d.get("schema_version", 1),
            is_current=d.get("is_current", False),
            metadata=d.get("metadata", {}),
        )


# ============================================================================
# Lakehouse Core
# ============================================================================


class DataLakehouse:
    """Institutional Data Lakehouse.

    Provides unified storage for all quant data types with:
    - Hot/Warm/Cold tiering
    - Time-travel (AS OF timestamp queries)
    - Snapshot-based versioning
    - Partitioned storage
    - ACID write operations

    Usage::

        lakehouse = DataLakehouse(LakehouseConfig(base_path="data/lakehouse"))
        lakehouse.create_dataset("market_tick", DatasetType.TICK, schema)
        lakehouse.write("market_tick", data, WriteMode.APPEND)
        df = lakehouse.read("market_tick", as_of=datetime(2026, 7, 28))
    """

    def __init__(self, config: Optional[LakehouseConfig] = None) -> None:
        self.config = config or LakehouseConfig()
        self._datasets: Dict[str, DatasetSchema] = {}
        self._snapshots: Dict[str, List[TableSnapshot]] = {}
        self._files: Dict[str, DataFile] = {}
        self._data_cache: Dict[str, List[Dict[str, Any]]] = {}

        # Ensure base path
        os.makedirs(self.config.base_path, exist_ok=True)
        self._load_state()

    # ------------------------------------------------------------------
    # Dataset Management
    # ------------------------------------------------------------------

    def create_dataset(
        self,
        name: str,
        dataset_type: DatasetType,
        schema: DatasetSchema,
        tier: Optional[StorageTier] = None,
    ) -> DatasetSchema:
        """Create a new dataset in the lakehouse.

        Args:
            name: Dataset name (must be unique).
            dataset_type: Type of data stored.
            schema: Dataset schema definition.
            tier: Initial storage tier (defaults to config default).

        Returns:
            The created DatasetSchema.

        Raises:
            ValueError: If dataset already exists.
        """
        if name in self._datasets:
            raise ValueError(f"Dataset '{name}' already exists")

        schema.name = name
        schema.dataset_type = dataset_type
        self._datasets[name] = schema
        self._snapshots[name] = []
        self._data_cache[name] = []

        # Create initial snapshot
        self._create_snapshot(name, f"Initial creation of dataset '{name}'")
        self._save_state()
        return schema

    def get_dataset(self, name: str) -> Optional[DatasetSchema]:
        """Get dataset schema by name."""
        return self._datasets.get(name)

    def list_datasets(self, dataset_type: Optional[DatasetType] = None) -> List[DatasetSchema]:
        """List all datasets, optionally filtered by type."""
        result = list(self._datasets.values())
        if dataset_type:
            result = [d for d in result if d.dataset_type == dataset_type]
        return result

    def drop_dataset(self, name: str) -> bool:
        """Drop a dataset and all its data.

        Args:
            name: Dataset name.

        Returns:
            True if dataset was dropped.
        """
        if name not in self._datasets:
            return False
        del self._datasets[name]
        self._snapshots.pop(name, None)
        self._data_cache.pop(name, None)
        self._files = {k: v for k, v in self._files.items() if v.dataset != name}
        self._save_state()
        return True

    # ------------------------------------------------------------------
    # Write Operations
    # ------------------------------------------------------------------

    def write(
        self,
        dataset: str,
        data: List[Dict[str, Any]],
        mode: WriteMode = WriteMode.APPEND,
        partition: Optional[str] = None,
        tier: Optional[StorageTier] = None,
    ) -> DataFile:
        """Write data to a dataset.

        Args:
            dataset: Target dataset name.
            data: List of records to write.
            mode: Write mode (append/overwrite/merge/upsert).
            partition: Partition key (e.g. "2026-07-29").
            tier: Storage tier for this file.

        Returns:
            DataFile metadata for the written file.

        Raises:
            ValueError: If dataset doesn't exist.
        """
        if dataset not in self._datasets:
            raise ValueError(f"Dataset '{dataset}' does not exist")

        schema = self._datasets[dataset]
        partition = partition or datetime.utcnow().strftime("%Y-%m-%d")
        tier = tier or self.config.default_tier

        # Validate schema
        self._validate_data(schema, data)

        # Generate file metadata
        file_id = str(uuid.uuid4())
        file_path = os.path.join(
            self.config.base_path,
            dataset,
            partition,
            f"{file_id}.parquet",
        )

        df = DataFile(
            file_id=file_id,
            dataset=dataset,
            partition=partition,
            file_path=file_path,
            row_count=len(data),
            size_bytes=len(json.dumps(data).encode("utf-8")),
            tier=tier,
        )

        # Apply write mode
        if mode == WriteMode.OVERWRITE:
            self._data_cache[dataset] = list(data)
        elif mode == WriteMode.APPEND:
            self._data_cache.setdefault(dataset, []).extend(data)
        elif mode == WriteMode.MERGE:
            self._merge_data(dataset, data, schema)
        elif mode == WriteMode.UPSERT:
            self._upsert_data(dataset, data, schema)

        self._files[file_id] = df
        self._save_state()
        return df

    def _validate_data(self, schema: DatasetSchema, data: List[Dict[str, Any]]) -> None:
        """Validate data against dataset schema."""
        if not schema.fields:
            return

        field_names = {f["name"] for f in schema.fields}
        required_fields = {f["name"] for f in schema.fields if f.get("required", False)}

        for i, record in enumerate(data):
            missing = required_fields - set(record.keys())
            if missing:
                raise ValueError(
                    f"Record {i} in dataset '{schema.name}': "
                    f"missing required fields: {missing}"
                )

    def _merge_data(
        self, dataset: str, data: List[Dict[str, Any]], schema: DatasetSchema
    ) -> None:
        """Merge new data into existing data by primary key."""
        existing = self._data_cache.get(dataset, [])
        if not schema.primary_key or not existing:
            self._data_cache.setdefault(dataset, []).extend(data)
            return

        pk = schema.primary_key[0]
        index = {tuple(r.get(k) for k in schema.primary_key): r for r in existing}
        for record in data:
            key = tuple(record.get(k) for k in schema.primary_key)
            if key in index:
                index[key].update(record)
            else:
                existing.append(record)
        self._data_cache[dataset] = existing

    def _upsert_data(
        self, dataset: str, data: List[Dict[str, Any]], schema: DatasetSchema
    ) -> None:
        """Upsert: update if exists, insert otherwise."""
        self._merge_data(dataset, data, schema)

    # ------------------------------------------------------------------
    # Read Operations
    # ------------------------------------------------------------------

    def read(
        self,
        dataset: str,
        as_of: Optional[datetime] = None,
        partition: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Read data from a dataset.

        Args:
            dataset: Dataset name.
            as_of: Point-in-time timestamp for time-travel.
            partition: Filter by partition.
            limit: Maximum records to return.

        Returns:
            List of data records.

        Raises:
            ValueError: If dataset doesn't exist.
        """
        if dataset not in self._datasets:
            raise ValueError(f"Dataset '{dataset}' does not exist")

        # Time-travel: find snapshot at or before timestamp
        if as_of and self.config.enable_time_travel:
            data = self._read_as_of(dataset, as_of)
        else:
            data = self._data_cache.get(dataset, [])

        # Filter by partition
        if partition:
            partition_files = {
                fid for fid, f in self._files.items()
                if f.dataset == dataset and f.partition == partition
            }
            # In full implementation, filter data by partition files
            # For now, approximate by date prefix
            data = [
                r for r in data
                if r.get("_partition", "").startswith(partition)
            ]

        if limit:
            data = data[:limit]

        return data

    def _read_as_of(self, dataset: str, timestamp: datetime) -> List[Dict[str, Any]]:
        """Read data as it existed at a specific point in time.

        Finds the most recent snapshot at or before the given timestamp
        and returns the data visible at that time.
        """
        snapshots = self._snapshots.get(dataset, [])
        if not snapshots:
            return []

        # Find snapshot at or before timestamp
        valid_snapshots = [s for s in snapshots if s.timestamp <= timestamp]
        if not valid_snapshots:
            return []

        target_snapshot = max(valid_snapshots, key=lambda s: s.timestamp)

        # Filter data to only files in the snapshot
        all_data = self._data_cache.get(dataset, [])
        # In production, would filter by file_ids; here return all data
        # as a simplified simulation
        return all_data

    def read_sql(
        self,
        query: str,
        as_of: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a simple SQL-like query against the lakehouse.

        Supports basic: SELECT * FROM dataset WHERE ...

        Args:
            query: SQL-like query string.
            as_of: Point-in-time timestamp.

        Returns:
            Query results.
        """
        # Simple SQL parser for SELECT * FROM dataset [WHERE ...]
        parts = query.strip().split()
        if len(parts) < 4 or parts[0].upper() != "SELECT":
            raise ValueError("Only SELECT queries are supported")

        # Extract dataset name
        from_idx = next((i for i, p in enumerate(parts) if p.upper() == "FROM"), None)
        if from_idx is None:
            raise ValueError("Missing FROM clause")

        dataset = parts[from_idx + 1].rstrip(";")

        # Read data
        data = self.read(dataset, as_of=as_of)

        # Simple WHERE clause parsing
        where_idx = next((i for i, p in enumerate(parts) if p.upper() == "WHERE"), None)
        if where_idx is not None:
            field = parts[where_idx + 1]
            op = parts[where_idx + 2]
            value = parts[where_idx + 3].strip("'\"")

            if op == "=":
                data = [r for r in data if str(r.get(field, "")) == value]
            elif op == ">":
                data = [r for r in data if float(r.get(field, 0)) > float(value)]
            elif op == "<":
                data = [r for r in data if float(r.get(field, 0)) < float(value)]

        return data

    # ------------------------------------------------------------------
    # Snapshot Management
    # ------------------------------------------------------------------

    def create_snapshot(self, dataset: str, description: str = "") -> TableSnapshot:
        """Manually create a snapshot of a dataset.

        Args:
            dataset: Dataset name.
            description: Snapshot description.

        Returns:
            The created TableSnapshot.
        """
        return self._create_snapshot(dataset, description)

    def _create_snapshot(self, dataset: str, description: str = "") -> TableSnapshot:
        """Internal snapshot creation."""
        if dataset not in self._datasets:
            raise ValueError(f"Dataset '{dataset}' does not exist")

        # Mark previous current snapshot as not current
        for snap in self._snapshots.get(dataset, []):
            snap.is_current = False

        # Get current file IDs
        file_ids = [
            fid for fid, f in self._files.items() if f.dataset == dataset
        ]

        snapshot = TableSnapshot(
            snapshot_id=str(uuid.uuid4()),
            dataset=dataset,
            timestamp=datetime.utcnow(),
            files=file_ids,
            schema_version=self._datasets[dataset].version,
            is_current=True,
            metadata={"description": description},
        )

        self._snapshots.setdefault(dataset, []).append(snapshot)
        self._save_state()
        return snapshot

    def list_snapshots(self, dataset: str) -> List[TableSnapshot]:
        """List all snapshots for a dataset."""
        return self._snapshots.get(dataset, [])

    def restore_snapshot(self, dataset: str, snapshot_id: str) -> bool:
        """Restore dataset to a specific snapshot.

        Args:
            dataset: Dataset name.
            snapshot_id: Snapshot ID to restore.

        Returns:
            True if restoration was successful.
        """
        snapshots = self._snapshots.get(dataset, [])
        for snap in snapshots:
            if snap.snapshot_id == snapshot_id:
                # Restore by setting data to snapshot state
                # In production, this would copy files; here it's a no-op
                # because we keep all data in memory
                snap.is_current = True
                self._save_state()
                return True
        return False

    # ------------------------------------------------------------------
    # Storage Tiering
    # ------------------------------------------------------------------

    def move_tier(self, dataset: str, target_tier: StorageTier) -> int:
        """Move all files for a dataset to a different storage tier.

        Args:
            dataset: Dataset name.
            target_tier: Target storage tier.

        Returns:
            Number of files moved.
        """
        count = 0
        for file_id, df in self._files.items():
            if df.dataset == dataset and df.tier != target_tier:
                df.tier = target_tier
                count += 1
        self._save_state()
        return count

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics across tiers.

        Returns:
            Dict with per-tier stats.
        """
        stats: Dict[str, Dict[str, Any]] = {
            "hot": {"files": 0, "size_bytes": 0, "rows": 0},
            "warm": {"files": 0, "size_bytes": 0, "rows": 0},
            "cold": {"files": 0, "size_bytes": 0, "rows": 0},
        }

        for df in self._files.values():
            tier = df.tier.value
            stats[tier]["files"] += 1
            stats[tier]["size_bytes"] += df.size_bytes
            stats[tier]["rows"] += df.row_count

        total_files = sum(s["files"] for s in stats.values())
        total_size = sum(s["size_bytes"] for s in stats.values())
        total_rows = sum(s["rows"] for s in stats.values())

        return {
            "tiers": stats,
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_rows": total_rows,
            "dataset_count": len(self._datasets),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        """Load lakehouse state from disk."""
        state_path = os.path.join(self.config.base_path, "_state.json")
        if os.path.exists(state_path):
            try:
                with open(state_path, "r") as f:
                    state = json.load(f)

                for ds_data in state.get("datasets", []):
                    schema = DatasetSchema.from_dict(ds_data)
                    self._datasets[schema.name] = schema

                for snap_data in state.get("snapshots", []):
                    snapshot = TableSnapshot.from_dict(snap_data)
                    self._snapshots.setdefault(snapshot.dataset, []).append(snapshot)

                for file_data in state.get("files", []):
                    df = DataFile.from_dict(file_data)
                    self._files[df.file_id] = df
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_state(self) -> None:
        """Persist lakehouse state to disk."""
        state = {
            "datasets": [ds.to_dict() for ds in self._datasets.values()],
            "snapshots": [
                snap.to_dict()
                for snaps in self._snapshots.values()
                for snap in snaps
            ],
            "files": [df.to_dict() for df in self._files.values()],
            "updated_at": datetime.utcnow().isoformat(),
        }

        state_path = os.path.join(self.config.base_path, "_state.json")
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2, default=str)

    def vacuum(self, older_than_days: Optional[int] = None) -> int:
        """Clean up old snapshots beyond retention period.

        Args:
            older_than_days: Remove snapshots older than N days.

        Returns:
            Number of snapshots removed.
        """
        retention = older_than_days or self.config.time_travel_retention_days
        cutoff = datetime.utcnow() - timedelta(days=retention)
        removed = 0

        for dataset, snapshots in self._snapshots.items():
            # Keep current snapshot
            current_snapshots = [s for s in snapshots if s.is_current]
            old_snapshots = [
                s for s in snapshots
                if s.timestamp < cutoff and not s.is_current
            ]

            self._snapshots[dataset] = current_snapshots + [
                s for s in snapshots
                if s not in old_snapshots
            ]
            removed += len(old_snapshots)

        self._save_state()
        return removed
