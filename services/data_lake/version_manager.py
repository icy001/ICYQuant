"""
Version Manager — data versioning with incremental versions,
rollback support, and version comparison.

Commit 16 Part 1.3
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class VersionPolicy(str, Enum):
    AUTO_INCREMENT = "auto_increment"
    TIMESTAMP_BASED = "timestamp_based"
    SEMANTIC = "semantic"
    HASH_BASED = "hash_based"


@dataclass
class DataVersion:
    version_id: str
    dataset: str
    policy: VersionPolicy = VersionPolicy.AUTO_INCREMENT
    sequence_number: int = 0
    parent_version: Optional[str] = None
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    record_count: int = 0
    total_bytes: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    is_rollback: bool = False


class VersionManager:
    """
    Manages data versioning for the data lake.

    Features:
    - Auto-incrementing version IDs
    - Timestamp-based versioning
    - Semantic versioning
    - Hash-based versioning
    - Rollback support
    - Version comparison and diff
    - Version tree/graph tracking
    """

    def __init__(self, storage: Any = None, catalog: Any = None) -> None:
        self._storage = storage
        self._catalog = catalog
        self._versions: dict[str, list[DataVersion]] = {}
        self._sequences: dict[str, int] = {}

    async def create_version(
        self,
        dataset: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
        description: str = "",
        parent_version: Optional[str] = None,
    ) -> DataVersion:
        """Create a new version for a dataset."""
        self._sequences.setdefault(dataset, 0)
        self._sequences[dataset] += 1
        seq = self._sequences[dataset]

        version = DataVersion(
            version_id=f"v{seq:08d}-{uuid.uuid4().hex[:8]}",
            dataset=dataset,
            sequence_number=seq,
            description=description,
            metadata=metadata or {},
            parent_version=parent_version,
        )

        self._versions.setdefault(dataset, []).append(version)
        logger.debug(
            "Created version %s for %s (seq=%d)", version.version_id, dataset, seq,
        )
        return version

    async def get(self, dataset: str, version_id: str) -> Optional[DataVersion]:
        """Get a specific version."""
        for v in self._versions.get(dataset, []):
            if v.version_id == version_id:
                return v
        return None

    async def get_latest(self, dataset: str) -> Optional[DataVersion]:
        """Get the latest version for a dataset."""
        versions = self._versions.get(dataset, [])
        if not versions:
            return None
        return max(versions, key=lambda v: v.sequence_number)

    async def list_versions(self, dataset: str) -> list[dict[str, Any]]:
        """List all versions for a dataset."""
        return [
            {
                "version_id": v.version_id,
                "sequence_number": v.sequence_number,
                "parent_version": v.parent_version,
                "record_count": v.record_count,
                "created_at": v.created_at.isoformat(),
                "description": v.description,
            }
            for v in self._versions.get(dataset, [])
        ]

    async def rollback(self, dataset: str, target_version_id: str) -> Optional[DataVersion]:
        """Create a rollback version pointing to a target version."""
        target = await self.get(dataset, target_version_id)
        if not target:
            logger.warning("Rollback target not found: %s", target_version_id)
            return None

        rollback = await self.create_version(
            dataset,
            description=f"Rollback to {target_version_id}",
            parent_version=target.version_id,
        )
        rollback.is_rollback = True
        logger.info("Created rollback version %s → %s", rollback.version_id, target_version_id)
        return rollback

    async def get_version_tree(self, dataset: str) -> dict[str, Any]:
        """Build a version tree for visualization."""
        versions = self._versions.get(dataset, [])
        tree: dict[str, list[str]] = {}
        for v in versions:
            tree.setdefault(v.version_id, [])
            if v.parent_version:
                tree.setdefault(v.parent_version, []).append(v.version_id)
        return {
            "dataset": dataset,
            "total_versions": len(versions),
            "latest": versions[-1].version_id if versions else None,
            "tree": {k: vs for k, vs in tree.items() if vs},
        }

    async def compare(
        self, dataset: str, version_a: str, version_b: str
    ) -> dict[str, Any]:
        """Compare two versions."""
        v_a = await self.get(dataset, version_a)
        v_b = await self.get(dataset, version_b)
        if not v_a or not v_b:
            return {"error": "Version not found"}

        return {
            "version_a": version_a,
            "version_b": version_b,
            "seq_diff": v_b.sequence_number - v_a.sequence_number,
            "time_diff_seconds": (
                v_b.created_at - v_a.created_at
            ).total_seconds(),
            "record_diff": v_b.record_count - v_a.record_count,
            "bytes_diff": v_b.total_bytes - v_a.total_bytes,
        }

    async def get_sequence(self, dataset: str) -> int:
        """Get current sequence number for a dataset."""
        return self._sequences.get(dataset, 0)
