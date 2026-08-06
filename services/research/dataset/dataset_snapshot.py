"""Dataset Snapshot — immutable point-in-time capture of dataset state.

Snapshots enable reproducible research by freezing dataset state
at specific points in time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class SnapshotType(str, Enum):
    """Types of dataset snapshots."""

    FULL = "full"           # Complete dataset copy
    INCREMENTAL = "incremental"  # Delta since last snapshot
    METADATA = "metadata"   # Schema + statistics only


@dataclass
class DatasetSnapshot:
    """Immutable point-in-time capture of a dataset.

    Supports:
    * Full data snapshots for exact reproduction
    * Incremental snapshots for efficiency
    * Metadata snapshots for lightweight tracking

    Usage::

        Dataset V1 → Dataset V2 → Dataset Snapshot → Rollback
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    dataset_id: str = ""
    version: int = 1
    snapshot_type: SnapshotType = SnapshotType.FULL
    description: str = ""
    row_count: int = 0
    size_bytes: int = 0
    checksum: str = ""
    storage_path: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "dataset_id": self.dataset_id,
            "version": self.version,
            "snapshot_type": self.snapshot_type.value,
            "description": self.description,
            "row_count": self.row_count,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "storage_path": self.storage_path,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatasetSnapshot":
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            id=data.get("id", str(uuid4())),
            dataset_id=data.get("dataset_id", ""),
            version=data.get("version", 1),
            snapshot_type=SnapshotType(data.get("snapshot_type", "full")),
            description=data.get("description", ""),
            row_count=data.get("row_count", 0),
            size_bytes=data.get("size_bytes", 0),
            checksum=data.get("checksum", ""),
            storage_path=data.get("storage_path", ""),
            created_at=created_at or datetime.now(timezone.utc),
            created_by=data.get("created_by"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return f"DatasetSnapshot(dataset={self.dataset_id[:8]}, v{self.version}, type={self.snapshot_type.value})"
