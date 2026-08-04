"""
Feature flag version management.

Provides version tracking, diff computation,
audit trail, and release management for
feature flag configurations.

Supports:
    - Version history tracking
    - Diff between versions
    - Release management
    - Audit trail for all version changes
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class VersionEntry:
    """
    A single version entry in the version history.

    Records the state of all feature flags at
    a specific point in time.

    Attributes:
        version: Version number.
        timestamp: When this version was created.
        operator: Who created this version.
        reason: Why this version was created.
        flag_keys: List of flag keys in this version.
        diff_summary: Summary of changes from previous version.
        metadata: Additional metadata.
    """

    version: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    operator: str = "system"
    reason: str = ""
    flag_keys: List[str] = field(default_factory=list)
    diff_summary: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "operator": self.operator,
            "reason": self.reason,
            "flag_keys": self.flag_keys,
            "diff_summary": self.diff_summary,
            "metadata": self.metadata,
        }


class VersionManager:
    """
    Manages feature flag version history.

    Tracks all changes to feature flags
    and provides version comparison,
    rollback, and audit capabilities.

    Usage:
        vm = VersionManager()
        entry = await vm.publish(flags, operator="admin", reason="update")
        diff = vm.diff(version_a, version_b)
        await vm.rollback(version=5)
    """

    def __init__(
        self,
        max_history: int = 100,
    ) -> None:
        """
        Initialize version manager.

        Args:
            max_history: Maximum number of version entries to retain.
        """
        self._entries: List[VersionEntry] = []
        self._max_history = max_history
        self._next_version = 1
        self._lock = asyncio.Lock()
        self._flag_snapshots: Dict[int, Dict[str, Any]] = {}

    async def publish(
        self,
        flag_data: Dict[str, Dict[str, Any]],
        operator: str = "system",
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VersionEntry:
        """
        Publish a new version of feature flags.

        Args:
            flag_data: Current flag data dictionary.
            operator: Who performed the change.
            reason: Why the change was made.
            metadata: Additional metadata.

        Returns:
            The new VersionEntry.
        """
        async with self._lock:
            old_flags = self._flag_snapshots.get(
                self._next_version - 1, {}
            )
            diff = self._compute_diff(old_flags, flag_data)

            entry = VersionEntry(
                version=self._next_version,
                operator=operator,
                reason=reason,
                flag_keys=sorted(flag_data.keys()),
                diff_summary=diff,
                metadata=metadata or {},
            )

            self._entries.append(entry)
            self._flag_snapshots[self._next_version] = dict(flag_data)
            self._next_version += 1

            # Trim history
            if len(self._entries) > self._max_history:
                old_versions = [
                    e.version
                    for e in self._entries[: len(self._entries) - self._max_history]
                ]
                self._entries = self._entries[-self._max_history:]
                for v in old_versions:
                    self._flag_snapshots.pop(v, None)

            logger.info(
                "Published version %d with %d flags (operator=%s, reason=%s)",
                entry.version,
                len(flag_data),
                operator,
                reason,
            )
            return entry

    async def rollback(
        self,
        version: int,
        operator: str = "system",
        reason: str = "rollback",
    ) -> Optional[VersionEntry]:
        """
        Rollback to a specific version.

        Creates a new version entry that restores
        the state from the specified version.

        Args:
            version: Version to rollback to.
            operator: Who performed the rollback.
            reason: Why the rollback was performed.

        Returns:
            New VersionEntry for the rollback, or None if version not found.
        """
        async with self._lock:
            if version not in self._flag_snapshots:
                logger.warning(
                    "Rollback failed: version %d not found", version,
                )
                return None

            restored = self._flag_snapshots[version]
            current_flags = self._flag_snapshots.get(
                self._next_version - 1, {}
            )
            diff = self._compute_diff(current_flags, restored)

            entry = VersionEntry(
                version=self._next_version,
                operator=operator,
                reason=f"rollback to v{version}: {reason}",
                flag_keys=sorted(restored.keys()),
                diff_summary=diff,
                metadata={"rollback_target": version},
            )

            self._entries.append(entry)
            self._flag_snapshots[self._next_version] = dict(restored)
            self._next_version += 1

            # Trim history
            if len(self._entries) > self._max_history:
                old_versions = [
                    e.version
                    for e in self._entries[: len(self._entries) - self._max_history]
                ]
                self._entries = self._entries[-self._max_history:]
                for v in old_versions:
                    self._flag_snapshots.pop(v, None)

            logger.info(
                "Rolled back to version %d (new version %d)",
                version,
                entry.version,
            )
            return entry

    def diff(
        self,
        version_a: int,
        version_b: int,
    ) -> Dict[str, Any]:
        """
        Compute diff between two versions.

        Args:
            version_a: First version.
            version_b: Second version.

        Returns:
            Diff dictionary.
        """
        flags_a = self._flag_snapshots.get(version_a, {})
        flags_b = self._flag_snapshots.get(version_b, {})

        if not flags_a and not flags_b:
            return {"error": "versions not found"}

        return self._compute_diff(flags_a, flags_b)

    def _compute_diff(
        self,
        old_flags: Dict[str, Any],
        new_flags: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compute difference between two flag sets."""
        added = []
        removed = []
        modified = []

        for key in new_flags:
            if key not in old_flags:
                added.append(key)
            elif old_flags[key] != new_flags[key]:
                modified.append({
                    "key": key,
                    "old": old_flags[key],
                    "new": new_flags[key],
                })

        for key in old_flags:
            if key not in new_flags:
                removed.append(key)

        return {
            "added": added,
            "removed": removed,
            "modified": modified,
            "added_count": len(added),
            "removed_count": len(removed),
            "modified_count": len(modified),
        }

    def get_version(self, version: int) -> Optional[Dict[str, Any]]:
        """
        Get flag data for a specific version.

        Args:
            version: Version number.

        Returns:
            Flag data dictionary or None.
        """
        return self._flag_snapshots.get(version)

    def get_current_version(self) -> int:
        """Get the current (latest) version number."""
        return self._next_version - 1 if self._next_version > 1 else 0

    def get_history(
        self,
        limit: int = 20,
    ) -> List[VersionEntry]:
        """
        Get recent version history.

        Args:
            limit: Max entries to return.

        Returns:
            List of VersionEntry objects (oldest first).
        """
        return list(self._entries)[-limit:]

    def get_entry(self, version: int) -> Optional[VersionEntry]:
        """
        Get a specific version entry.

        Args:
            version: Version number.

        Returns:
            VersionEntry or None.
        """
        for entry in self._entries:
            if entry.version == version:
                return entry
        return None

    def query(
        self,
        flag_key: Optional[str] = None,
        operator: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 50,
    ) -> List[VersionEntry]:
        """
        Query version history with filters.

        Args:
            flag_key: Filter by flag key.
            operator: Filter by operator.
            action: Filter by action type.
            limit: Max entries.

        Returns:
            Matching version entries.
        """
        results = list(reversed(self._entries))

        if flag_key:
            results = [
                e for e in results
                if flag_key in e.flag_keys
            ]
        if operator:
            results = [e for e in results if e.operator == operator]
        if action:
            results = [
                e for e in results
                if action in e.reason.lower()
            ]

        return results[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get version manager statistics."""
        return {
            "current_version": self.get_current_version(),
            "total_versions": len(self._entries),
            "max_history": self._max_history,
            "snapshots_stored": len(self._flag_snapshots),
        }
