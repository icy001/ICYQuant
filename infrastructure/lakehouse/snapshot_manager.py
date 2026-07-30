"""ICYQuant Snapshot Manager.

Manages point-in-time snapshots of lakehouse state.
Supports:
    - Incremental snapshots (only changed files)
    - Snapshot isolation for concurrent reads
    - Snapshot expiration and cleanup
    - Snapshot diff and comparison
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class SnapshotType(str, Enum):
    """Types of snapshots."""

    FULL = "full"            # Complete state snapshot
    INCREMENTAL = "incremental"  # Changes since last snapshot
    CHECKPOINT = "checkpoint"    # Recovery checkpoint


@dataclass
class Snapshot:
    """A lakehouse snapshot."""

    snapshot_id: str
    snapshot_type: SnapshotType = SnapshotType.FULL
    parent_snapshot_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    file_manifest: Dict[str, str] = field(default_factory=dict)  # file_id → file_path
    added_files: List[str] = field(default_factory=list)
    removed_files: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_current: bool = False
    is_expired: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "snapshot_type": self.snapshot_type.value,
            "parent_snapshot_id": self.parent_snapshot_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "file_count": len(self.file_manifest),
            "added_files": self.added_files,
            "removed_files": self.removed_files,
            "is_current": self.is_current,
            "is_expired": self.is_expired,
        }


@dataclass
class SnapshotDiff:
    """Difference between two snapshots."""

    snapshot_a: str
    snapshot_b: str
    added_files: List[str] = field(default_factory=list)
    removed_files: List[str] = field(default_factory=list)
    modified_files: List[str] = field(default_factory=list)
    total_changes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_a": self.snapshot_a,
            "snapshot_b": self.snapshot_b,
            "added_files": self.added_files,
            "removed_files": self.removed_files,
            "modified_files": self.modified_files,
            "total_changes": self.total_changes,
        }


class SnapshotManager:
    """Lakehouse Snapshot Manager.

    Creates and manages snapshots for point-in-time recovery
    and concurrent read isolation.

    Usage::

        mgr = SnapshotManager(retention_days=30)
        snap = mgr.create_snapshot(file_manifest, snapshot_type=SnapshotType.FULL)
        mgr.set_current(snap.snapshot_id)
        diff = mgr.diff_snapshots(snap1.snapshot_id, snap2.snapshot_id)
    """

    def __init__(
        self,
        retention_days: int = 30,
        max_snapshots: int = 100,
    ) -> None:
        self.retention_days = retention_days
        self.max_snapshots = max_snapshots
        self._snapshots: Dict[str, Snapshot] = {}
        self._current_snapshot_id: Optional[str] = None
        self._snapshot_chain: Dict[str, str] = {}  # child → parent

    # ------------------------------------------------------------------
    # Snapshot Creation
    # ------------------------------------------------------------------

    def create_snapshot(
        self,
        file_manifest: Dict[str, str],
        snapshot_type: SnapshotType = SnapshotType.FULL,
        parent_snapshot_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Snapshot:
        """Create a new snapshot.

        Args:
            file_manifest: Dict mapping file_id → file_path.
            snapshot_type: Type of snapshot.
            parent_snapshot_id: Parent snapshot for incremental snapshots.
            metadata: Additional metadata.

        Returns:
            Snapshot.
        """
        snapshot_id = str(uuid.uuid4())

        # For incremental, compute delta from parent
        added_files: List[str] = []
        removed_files: List[str] = []

        if snapshot_type == SnapshotType.INCREMENTAL and parent_snapshot_id:
            parent = self._snapshots.get(parent_snapshot_id)
            if parent:
                parent_files = set(parent.file_manifest.keys())
                current_files = set(file_manifest.keys())
                added_files = list(current_files - parent_files)
                removed_files = list(parent_files - current_files)

        snapshot = Snapshot(
            snapshot_id=snapshot_id,
            snapshot_type=snapshot_type,
            parent_snapshot_id=parent_snapshot_id,
            file_manifest=dict(file_manifest),
            added_files=added_files,
            removed_files=removed_files,
            metadata=metadata or {},
            expires_at=datetime.utcnow() + timedelta(days=self.retention_days),
        )

        self._snapshots[snapshot_id] = snapshot

        if parent_snapshot_id:
            self._snapshot_chain[snapshot_id] = parent_snapshot_id

        return snapshot

    def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        """Get a snapshot by ID."""
        return self._snapshots.get(snapshot_id)

    def set_current(self, snapshot_id: str) -> bool:
        """Set a snapshot as the current state.

        Args:
            snapshot_id: Snapshot ID.

        Returns:
            True if set.
        """
        if snapshot_id not in self._snapshots:
            return False

        # Mark previous current as not current
        if self._current_snapshot_id:
            prev = self._snapshots.get(self._current_snapshot_id)
            if prev:
                prev.is_current = False

        self._current_snapshot_id = snapshot_id
        self._snapshots[snapshot_id].is_current = True
        return True

    def get_current(self) -> Optional[Snapshot]:
        """Get the current snapshot."""
        if self._current_snapshot_id:
            return self._snapshots.get(self._current_snapshot_id)
        return None

    # ------------------------------------------------------------------
    # Snapshot Resolution
    # ------------------------------------------------------------------

    def resolve_files(self, snapshot_id: str) -> Dict[str, str]:
        """Resolve the complete file manifest for a snapshot.

        For incremental snapshots, walks the chain to compute
        the full file list.

        Args:
            snapshot_id: Snapshot ID.

        Returns:
            Dict of file_id → file_path.
        """
        snapshot = self._snapshots.get(snapshot_id)
        if not snapshot:
            return {}

        if snapshot.snapshot_type == SnapshotType.FULL:
            return dict(snapshot.file_manifest)

        # For incremental, walk the chain
        manifest: Dict[str, str] = {}
        current = snapshot

        while current:
            manifest.update(current.file_manifest)
            # Remove deleted files
            for fid in current.removed_files:
                manifest.pop(fid, None)

            if current.parent_snapshot_id:
                current = self._snapshots.get(current.parent_snapshot_id)
            else:
                break

        return manifest

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------

    def diff_snapshots(
        self, snapshot_id_a: str, snapshot_id_b: str
    ) -> Optional[SnapshotDiff]:
        """Compute the difference between two snapshots.

        Args:
            snapshot_id_a: First snapshot ID.
            snapshot_id_b: Second snapshot ID.

        Returns:
            SnapshotDiff or None.
        """
        snap_a = self._snapshots.get(snapshot_id_a)
        snap_b = self._snapshots.get(snapshot_id_b)

        if not snap_a or not snap_b:
            return None

        files_a = set(self.resolve_files(snapshot_id_a).keys())
        files_b = set(self.resolve_files(snapshot_id_b).keys())

        added = sorted(files_b - files_a)
        removed = sorted(files_a - files_b)

        diff = SnapshotDiff(
            snapshot_a=snapshot_id_a,
            snapshot_b=snapshot_id_b,
            added_files=added,
            removed_files=removed,
            modified_files=[],
            total_changes=len(added) + len(removed),
        )

        return diff

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def expire_snapshots(self) -> int:
        """Expire snapshots older than retention period.

        Returns:
            Number of snapshots expired.
        """
        now = datetime.utcnow()
        expired = 0

        for snap_id, snapshot in list(self._snapshots.items()):
            if snapshot.expires_at and snapshot.expires_at < now:
                snapshot.is_expired = True
                expired += 1

        return expired

    def prune_expired(self) -> int:
        """Remove expired snapshots.

        Returns:
            Number of snapshots pruned.
        """
        to_remove = [
            sid for sid, snap in self._snapshots.items()
            if snap.is_expired and not snap.is_current
        ]

        for sid in to_remove:
            del self._snapshots[sid]
            self._snapshot_chain.pop(sid, None)

        return len(to_remove)

    def enforce_max_snapshots(self) -> int:
        """Remove oldest snapshots if over the maximum limit.

        Returns:
            Number of snapshots removed.
        """
        if len(self._snapshots) <= self.max_snapshots:
            return 0

        # Sort by creation time, keep newest
        sorted_snaps = sorted(
            self._snapshots.values(),
            key=lambda s: s.created_at,
            reverse=True,
        )

        to_keep = sorted_snaps[:self.max_snapshots]
        keep_ids = {s.snapshot_id for s in to_keep}

        removed = 0
        for sid in list(self._snapshots.keys()):
            if sid not in keep_ids and not self._snapshots[sid].is_current:
                del self._snapshots[sid]
                self._snapshot_chain.pop(sid, None)
                removed += 1

        return removed

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list_snapshots(
        self,
        snapshot_type: Optional[SnapshotType] = None,
        include_expired: bool = False,
    ) -> List[Snapshot]:
        """List snapshots with optional filters."""
        snapshots = list(self._snapshots.values())

        if snapshot_type:
            snapshots = [s for s in snapshots if s.snapshot_type == snapshot_type]
        if not include_expired:
            snapshots = [s for s in snapshots if not s.is_expired]

        snapshots.sort(key=lambda s: s.created_at, reverse=True)
        return snapshots

    def get_chain(self, snapshot_id: str) -> List[Snapshot]:
        """Get the chain of snapshots from root to this snapshot."""
        chain: List[Snapshot] = []
        current_id = snapshot_id

        while current_id:
            snapshot = self._snapshots.get(current_id)
            if not snapshot:
                break
            chain.insert(0, snapshot)
            current_id = snapshot.parent_snapshot_id

        return chain

    def get_stats(self) -> Dict[str, Any]:
        """Get snapshot statistics."""
        return {
            "total_snapshots": len(self._snapshots),
            "current_snapshot_id": self._current_snapshot_id,
            "by_type": {
                st.value: sum(
                    1 for s in self._snapshots.values()
                    if s.snapshot_type == st
                )
                for st in SnapshotType
            },
            "expired": sum(1 for s in self._snapshots.values() if s.is_expired),
            "total_files_tracked": len(
                self.resolve_files(self._current_snapshot_id)
                if self._current_snapshot_id else {}
            ),
        }
