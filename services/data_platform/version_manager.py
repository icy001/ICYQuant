"""ICYQuant Data Version Manager.

Manages data versioning and snapshots across the data platform.
Supports:
    - Daily / Weekly / Monthly snapshots
    - Point-in-time recovery
    - Snapshot comparison (diff)
    - Full lakehouse restore

Usage::

    vm = VersionManager(VersionConfig())
    snapshot = vm.create_snapshot("market_tick", "Daily snapshot")
    vm.restore_snapshot("market_tick", snapshot.snapshot_id)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from services.data_platform.config import (
    VersionConfig,
    SnapshotFrequency,
)
from services.data_platform.lakehouse import DataLakehouse, TableSnapshot


# ============================================================================
# Version Types
# ============================================================================


@dataclass
class VersionInfo:
    """Version metadata for a dataset."""

    dataset: str
    version_id: str
    version_number: int
    snapshot_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = "system"
    description: str = ""
    is_latest: bool = True
    parent_version: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset,
            "version_id": self.version_id,
            "version_number": self.version_number,
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "description": self.description,
            "is_latest": self.is_latest,
            "parent_version": self.parent_version,
            "metadata": self.metadata,
        }


@dataclass
class SnapshotDiff:
    """Difference between two snapshots."""

    dataset: str
    snapshot_a: str
    snapshot_b: str
    added_rows: int = 0
    removed_rows: int = 0
    modified_rows: int = 0
    added_columns: List[str] = field(default_factory=list)
    removed_columns: List[str] = field(default_factory=list)
    schema_changed: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset,
            "snapshot_a": self.snapshot_a,
            "snapshot_b": self.snapshot_b,
            "added_rows": self.added_rows,
            "removed_rows": self.removed_rows,
            "modified_rows": self.modified_rows,
            "added_columns": self.added_columns,
            "removed_columns": self.removed_columns,
            "schema_changed": self.schema_changed,
            "details": self.details,
        }


# ============================================================================
# Version Manager
# ============================================================================


class VersionManager:
    """Data Version Manager.

    Manages versioned snapshots of datasets for point-in-time recovery
    and historical comparison.

    Usage::

        vm = VersionManager(VersionConfig(), lakehouse)
        vm.create_version("market_tick", "Daily EOD snapshot")
        versions = vm.list_versions("market_tick")
        vm.restore_version("market_tick", "v3")
    """

    def __init__(
        self,
        config: Optional[VersionConfig] = None,
        lakehouse: Optional[DataLakehouse] = None,
    ) -> None:
        self.config = config or VersionConfig()
        self.lakehouse = lakehouse
        self._versions: Dict[str, List[VersionInfo]] = {}
        self._version_counter: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Version Management
    # ------------------------------------------------------------------

    def create_version(
        self,
        dataset: str,
        description: str = "",
        created_by: str = "system",
    ) -> VersionInfo:
        """Create a new versioned snapshot of a dataset.

        Args:
            dataset: Dataset name.
            description: Version description.
            created_by: Who created the version.

        Returns:
            VersionInfo for the new version.
        """
        # Create lakehouse snapshot first
        snapshot: Optional[TableSnapshot] = None
        if self.lakehouse:
            snapshot = self.lakehouse.create_snapshot(dataset, description)

        # Generate version number
        self._version_counter.setdefault(dataset, 0)
        self._version_counter[dataset] += 1
        version_number = self._version_counter[dataset]

        version_id = f"{dataset}_v{version_number}"

        # Mark previous latest as not latest
        if dataset in self._versions:
            for v in self._versions[dataset]:
                v.is_latest = False

        # Get parent version
        parent = None
        if dataset in self._versions and self._versions[dataset]:
            parent = self._versions[dataset][-1].version_id

        version = VersionInfo(
            dataset=dataset,
            version_id=version_id,
            version_number=version_number,
            snapshot_id=snapshot.snapshot_id if snapshot else "",
            created_by=created_by,
            description=description,
            parent_version=parent,
        )

        self._versions.setdefault(dataset, []).append(version)
        return version

    def get_version(self, dataset: str, version_id: str) -> Optional[VersionInfo]:
        """Get a specific version by ID."""
        versions = self._versions.get(dataset, [])
        for v in versions:
            if v.version_id == version_id:
                return v
        return None

    def get_latest_version(self, dataset: str) -> Optional[VersionInfo]:
        """Get the latest version of a dataset."""
        versions = self._versions.get(dataset, [])
        for v in reversed(versions):
            if v.is_latest:
                return v
        return versions[-1] if versions else None

    def list_versions(self, dataset: str) -> List[VersionInfo]:
        """List all versions of a dataset, oldest first."""
        return self._versions.get(dataset, [])

    def restore_version(self, dataset: str, version_id: str) -> bool:
        """Restore a dataset to a previous version.

        Args:
            dataset: Dataset name.
            version_id: Version ID to restore.

        Returns:
            True if restored successfully.
        """
        version = self.get_version(dataset, version_id)
        if not version:
            return False

        if self.lakehouse and version.snapshot_id:
            return self.lakehouse.restore_snapshot(dataset, version.snapshot_id)

        return True

    # ------------------------------------------------------------------
    # Snapshot Management
    # ------------------------------------------------------------------

    def create_scheduled_snapshots(self) -> Dict[str, VersionInfo]:
        """Create snapshots based on configured frequency.

        Called by scheduler (cron job).

        Returns:
            Dict mapping dataset to created VersionInfo.
        """
        created: Dict[str, VersionInfo] = {}

        if not self.lakehouse:
            return created

        for dataset in self.lakehouse._datasets:
            version = self.create_version(
                dataset,
                description=f"Scheduled snapshot ({self.config.snapshot_frequency.value})",
                created_by="scheduler",
            )
            created[dataset] = version

        return created

    def prune_old_snapshots(self) -> int:
        """Remove snapshots older than retention period.

        Returns:
            Number of versions pruned.
        """
        cutoff = datetime.utcnow() - timedelta(days=self.config.snapshot_retention_days)
        pruned = 0

        for dataset, versions in self._versions.items():
            # Keep at least one version
            keep = [v for v in versions if v.created_at >= cutoff or v.is_latest]
            removed = len(versions) - len(keep)
            self._versions[dataset] = keep
            pruned += removed

        if self.lakehouse:
            self.lakehouse.vacuum(older_than_days=self.config.snapshot_retention_days)

        return pruned

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------

    def diff_versions(
        self,
        dataset: str,
        version_a: str,
        version_b: str,
    ) -> Optional[SnapshotDiff]:
        """Compare two versions and return the difference.

        Args:
            dataset: Dataset name.
            version_a: First version ID.
            version_b: Second version ID.

        Returns:
            SnapshotDiff or None if versions not found.
        """
        v_a = self.get_version(dataset, version_a)
        v_b = self.get_version(dataset, version_b)

        if not v_a or not v_b:
            return None

        # Get data from both snapshots
        data_a: List[Dict[str, Any]] = []
        data_b: List[Dict[str, Any]] = []

        if self.lakehouse:
            data_a = self.lakehouse.read(dataset, as_of=v_a.created_at)
            data_b = self.lakehouse.read(dataset, as_of=v_b.created_at)

        diff = SnapshotDiff(
            dataset=dataset,
            snapshot_a=version_a,
            snapshot_b=version_b,
            added_rows=max(0, len(data_b) - len(data_a)),
            removed_rows=max(0, len(data_a) - len(data_b)),
            modified_rows=0,
        )

        # Compare schemas
        cols_a = set()
        cols_b = set()
        if data_a:
            cols_a = set(data_a[0].keys())
        if data_b:
            cols_b = set(data_b[0].keys())

        diff.added_columns = sorted(cols_b - cols_a)
        diff.removed_columns = sorted(cols_a - cols_b)
        diff.schema_changed = bool(diff.added_columns or diff.removed_columns)

        return diff

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Get version management statistics."""
        total_versions = sum(len(v) for v in self._versions.values())

        return {
            "total_datasets": len(self._versions),
            "total_versions": total_versions,
            "avg_versions_per_dataset": round(
                total_versions / len(self._versions), 1
            ) if self._versions else 0,
            "datasets": {
                ds: len(versions) for ds, versions in self._versions.items()
            },
        }
