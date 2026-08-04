"""
Feature flag snapshot management.

Provides immutable snapshot management for
feature flag configurations, supporting
atomic swap, rollback, and version comparison.

Snapshots are the foundation for lock-free
read-side access and hot reload.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class FeatureSnapshot:
    """
    Immutable snapshot of feature flag configuration.

    A snapshot captures the complete state of all
    feature flags at a point in time, enabling
    atomic read access and rollback.

    Attributes:
        version: Monotonically increasing version number.
        timestamp: When the snapshot was created.
        checksum: SHA-256 checksum of the snapshot data.
        flags: Dictionary of flag key -> flag data.
        metadata: Additional snapshot metadata.
    """

    version: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    checksum: str = ""
    flags: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize snapshot to dictionary."""
        return {
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "checksum": self.checksum,
            "flags_count": len(self.flags),
            "flags": self.flags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeatureSnapshot":
        """Create snapshot from dictionary."""
        return cls(
            version=data.get("version", 0),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if "timestamp" in data
            else datetime.utcnow(),
            checksum=data.get("checksum", ""),
            flags=data.get("flags", {}),
            metadata=data.get("metadata", {}),
        )

    def compute_checksum(self) -> str:
        """Compute SHA-256 checksum of snapshot data."""
        data_str = str(sorted(self.flags.items()))
        return hashlib.sha256(data_str.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify the snapshot checksum matches."""
        expected = self.compute_checksum()
        return self.checksum == expected

    def with_version(self, version: int) -> "FeatureSnapshot":
        """Create a copy with a new version number."""
        return FeatureSnapshot(
            version=version,
            timestamp=datetime.utcnow(),
            checksum=self.checksum,
            flags=dict(self.flags),
            metadata=dict(self.metadata),
        )

    def diff(self, other: "FeatureSnapshot") -> Dict[str, Any]:
        """
        Compute difference between this snapshot and another.

        Returns a dict with added, removed, and modified flags.
        """
        added = []
        removed = []
        modified = []

        for key in other.flags:
            if key not in self.flags:
                added.append(key)
            elif self.flags[key] != other.flags[key]:
                modified.append(key)

        for key in self.flags:
            if key not in other.flags:
                removed.append(key)

        return {
            "added": added,
            "removed": removed,
            "modified": modified,
            "old_version": self.version,
            "new_version": other.version,
        }


class SnapshotManager:
    """
    Manages feature flag snapshots.

    Supports creating snapshots, retrieving
    history, comparing versions, and rollback.
    Uses an atomic reference swap pattern
    for lock-free reads.

    Usage:
        mgr = SnapshotManager()
        snap = mgr.create_snapshot(flags)
        current = mgr.get_current()
        mgr.activate(snap)  # atomic swap
    """

    def __init__(
        self,
        max_history: int = 50,
    ) -> None:
        """
        Initialize snapshot manager.

        Args:
            max_history: Maximum number of historical snapshots to retain.
        """
        self._current: Optional[FeatureSnapshot] = None
        self._history: List[FeatureSnapshot] = []
        self._max_history = max_history
        self._next_version = 1
        self._global_lock = None  # Set during bootstrap

    def create_snapshot(
        self,
        flags: Dict[str, Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FeatureSnapshot:
        """
        Create a new snapshot from flag data.

        Args:
            flags: Dictionary of flag key -> flag data.
            metadata: Additional metadata.

        Returns:
            Newly created FeatureSnapshot.
        """
        version = self._next_version
        self._next_version += 1

        snap = FeatureSnapshot(
            version=version,
            timestamp=datetime.utcnow(),
            flags=dict(flags),
            metadata=metadata or {},
        )
        snap.checksum = snap.compute_checksum()
        return snap

    def get_current(self) -> Optional[FeatureSnapshot]:
        """
        Get the currently active snapshot.

        This is a lock-free read - returns the
        current reference immediately.

        Returns:
            Current FeatureSnapshot or None.
        """
        return self._current

    def get_version(self) -> int:
        """Get current snapshot version."""
        if self._current is None:
            return 0
        return self._current.version

    def activate(self, snapshot: FeatureSnapshot) -> None:
        """
        Atomically activate a new snapshot.

        This swaps the current reference without
        requiring read-side locks. All subsequent
        reads will see the new snapshot.

        Args:
            snapshot: Snapshot to activate.
        """
        snapshot.checksum = snapshot.compute_checksum()
        old = self._current
        self._current = snapshot

        if old is not None:
            self._history.append(old)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

    def rollback_to(self, version: int) -> Optional[FeatureSnapshot]:
        """
        Rollback to a specific version.

        Args:
            version: Version to rollback to.

        Returns:
            The rolled-back snapshot or None if version not found.
        """
        for snap in reversed(self._history):
            if snap.version == version:
                # Create a new snapshot with the old data but new version
                new_snap = snap.with_version(self._next_version)
                self._next_version += 1
                new_snap.checksum = new_snap.compute_checksum()
                self.activate(new_snap)
                return new_snap
        return None

    def compare(
        self,
        version_a: int,
        version_b: int,
    ) -> Dict[str, Any]:
        """
        Compare two historical versions.

        Args:
            version_a: First version.
            version_b: Second version.

        Returns:
            Diff dictionary between the two versions.
        """
        snap_a = self._find_version(version_a)
        snap_b = self._find_version(version_b)

        if snap_a is None or snap_b is None:
            return {"error": "version not found"}

        return snap_a.diff(snap_b)

    def _find_version(self, version: int) -> Optional[FeatureSnapshot]:
        """Find a snapshot by version number."""
        if self._current and self._current.version == version:
            return self._current
        for snap in self._history:
            if snap.version == version:
                return snap
        return None

    def get_history(
        self,
        limit: int = 20,
    ) -> List[FeatureSnapshot]:
        """
        Get recent snapshot history.

        Args:
            limit: Max number of historical snapshots.

        Returns:
            List of historical snapshots (oldest first).
        """
        return list(self._history)[-limit:]

    def clear_history(self) -> None:
        """Clear all historical snapshots."""
        self._history.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get snapshot manager statistics."""
        return {
            "current_version": self._current.version if self._current else 0,
            "history_count": len(self._history),
            "next_version": self._next_version,
            "flags_count": len(self._current.flags) if self._current else 0,
        }

    async def persist(self) -> None:
        """
        Persist current snapshot to storage.

        This is a placeholder for storage integration.
        Override or extend for actual persistence.
        """
        pass

    async def restore_from_storage(self) -> Optional[FeatureSnapshot]:
        """
        Restore the latest snapshot from storage.

        Returns:
            Restored snapshot or None.
        """
        return None
