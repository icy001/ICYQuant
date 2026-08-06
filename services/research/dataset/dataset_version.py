"""Dataset Version — version management for dataset evolution.

Tracks dataset versions to ensure research reproducibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class DatasetVersion:
    """Immutable version record of a dataset.

    Each version captures:
    * Schema at that point in time
    * Row/column counts
    * Checksum for integrity verification
    * Parent version for lineage
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    dataset_id: str = ""
    version: int = 1
    parent_version: Optional[int] = None
    schema_version: int = 1
    row_count: int = 0
    column_count: int = 0
    checksum: str = ""
    description: str = ""
    status: str = "active"  # active, superseded, deprecated
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_latest(self) -> bool:
        return self.status == "active"

    @property
    def version_label(self) -> str:
        return f"v{self.version}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "dataset_id": self.dataset_id,
            "version": self.version,
            "parent_version": self.parent_version,
            "schema_version": self.schema_version,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "checksum": self.checksum,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatasetVersion":
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            id=data.get("id", str(uuid4())),
            dataset_id=data.get("dataset_id", ""),
            version=data.get("version", 1),
            parent_version=data.get("parent_version"),
            schema_version=data.get("schema_version", 1),
            row_count=data.get("row_count", 0),
            column_count=data.get("column_count", 0),
            checksum=data.get("checksum", ""),
            description=data.get("description", ""),
            status=data.get("status", "active"),
            created_at=created_at or datetime.now(timezone.utc),
            created_by=data.get("created_by"),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return f"DatasetVersion(dataset={self.dataset_id[:8]}, {self.version_label})"
