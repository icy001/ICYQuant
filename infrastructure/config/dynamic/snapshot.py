"""
Dynamic configuration snapshot.

Extends ConfigurationSnapshot with version tracking,
checksums, and metadata for dynamic reload support.

Design:
    Immutable: Once created, cannot be modified.
    Thread-safe: Readers always see consistent snapshot.
    Versioned: Each snapshot has unique version number.
    Checksummed: Integrity verification via checksum.
"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class DynamicSnapshot:
    """
    Immutable dynamic configuration snapshot.

    Represents a complete configuration state with
    version tracking and integrity verification.

    Attributes:
        values: Configuration key-value pairs.
        version: Snapshot version number (monotonically increasing).
        environment: Deployment environment.
        sources_used: List of source names that contributed.
        created_at: Creation timestamp.
        checksum: SHA-256 checksum of values for integrity verification.
        metadata: Additional metadata (operator, reason, etc.).
        operator: Who triggered this change.
        reason: Reason for the change.
        parent_version: Previous snapshot version (for chain tracking).
    """

    values: Dict[str, Any] = field(default_factory=dict)
    version: int = 0
    environment: str = "development"
    sources_used: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    operator: str = "system"
    reason: str = ""
    parent_version: Optional[int] = None

    def __post_init__(self):
        """Calculate checksum after initialization."""
        if not hasattr(self, '_checksum'):
            self._checksum = self._calculate_checksum()

    def _calculate_checksum(
        self,
    ) -> str:
        """Calculate SHA-256 checksum of values."""
        normalized = json.dumps(
            self._sort_dict(self.values),
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(normalized.encode()).hexdigest()

    @staticmethod
    def _sort_dict(
        d: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Recursively sort dictionary keys."""
        return {
            k: DynamicSnapshot._sort_dict(v) if isinstance(v, dict) else v
            for k, v in sorted(d.items())
        }

    @property
    def checksum(
        self,
    ) -> str:
        """Get snapshot checksum."""
        return self._checksum

    def verify_integrity(
        self,
    ) -> bool:
        """Verify snapshot integrity via checksum."""
        return self._calculate_checksum() == self._checksum

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key.
            default: Default value if not found.

        Returns:
            Configuration value or default.
        """
        return self.values.get(key, default)

    def get_nested(
        self,
        key: str,
        default: Any = None,
        separator: str = ".",
    ) -> Any:
        """
        Get a nested configuration value.

        Args:
            key: Dotted key (e.g., "server.port").
            default: Default value if not found.
            separator: Key separator.

        Returns:
            Configuration value or default.
        """
        parts = key.split(separator)
        current: Any = self.values
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    def keys(
        self,
    ) -> List[str]:
        """Get all configuration keys."""
        return list(self.values.keys())

    def contains(
        self,
        key: str,
    ) -> bool:
        """Check if a key exists."""
        return key in self.values

    def diff_keys(
        self,
        other: "DynamicSnapshot",
    ) -> List[str]:
        """
        Get keys that differ between this and another snapshot.

        Args:
            other: Another snapshot.

        Returns:
            List of differing keys.
        """
        all_keys = set(self.values.keys()) | set(other.values.keys())
        changed = []
        for key in all_keys:
            if self.values.get(key) != other.values.get(key):
                changed.append(key)
        return sorted(changed)

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """Convert snapshot to dictionary."""
        return {
            "version": self.version,
            "environment": self.environment,
            "sources_used": self.sources_used,
            "created_at": self.created_at.isoformat(),
            "checksum": self.checksum,
            "operator": self.operator,
            "reason": self.reason,
            "parent_version": self.parent_version,
            "values": copy.deepcopy(self.values),
            "metadata": copy.deepcopy(self.metadata),
        }

    def deep_copy(
        self,
        new_version: Optional[int] = None,
    ) -> "DynamicSnapshot":
        """
        Create a deep copy with optional new version.

        Args:
            new_version: Optional new version number.

        Returns:
            New snapshot copy.
        """
        return DynamicSnapshot(
            values=copy.deepcopy(self.values),
            version=new_version or self.version,
            environment=self.environment,
            sources_used=list(self.sources_used),
            created_at=self.created_at,
            metadata=copy.deepcopy(self.metadata),
            operator=self.operator,
            reason=self.reason,
            parent_version=self.parent_version,
        )


class DynamicSnapshotStore:
    """
    Thread-safe store for dynamic configuration snapshots.

    Supports atomic snapshot swapping, version history,
    and rollback operations.

    Thread Safety:
    - Reads are lock-free (atomic reference)
    - Writes use a single lock
    - Snapshot swap is atomic
    """

    def __init__(
        self,
        max_history: int = 20,
    ) -> None:
        """
        Initialize snapshot store.

        Args:
            max_history: Maximum number of historical snapshots.
        """
        self._current: Optional[DynamicSnapshot] = None
        self._history: List[DynamicSnapshot] = []
        self._max_history = max_history
        self._lock = threading.Lock()
        self._version_counter = 0
        self._condition = threading.Condition(self._lock)

    @property
    def current(
        self,
    ) -> Optional[DynamicSnapshot]:
        """Get current snapshot (lock-free read)."""
        return self._current

    @property
    def version(
        self,
    ) -> int:
        """Get current version number."""
        return self._version_counter

    def update(
        self,
        values: Dict[str, Any],
        environment: str = "development",
        sources_used: Optional[List[str]] = None,
        operator: str = "system",
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DynamicSnapshot:
        """
        Create and atomically swap a new snapshot.

        Args:
            values: Configuration values.
            environment: Deployment environment.
            sources_used: List of source names.
            operator: Who triggered the change.
            reason: Reason for the change.
            metadata: Additional metadata.

        Returns:
            New snapshot.
        """
        with self._condition:
            old_version = self._current.version if self._current else None

            self._version_counter += 1

            # Save old snapshot to history
            if self._current is not None:
                self._history.append(self._current)
                if len(self._history) > self._max_history:
                    self._history.pop(0)

            # Create and swap new snapshot
            new_snapshot = DynamicSnapshot(
                values=copy.deepcopy(values),
                version=self._version_counter,
                environment=environment,
                sources_used=sources_used or [],
                operator=operator,
                reason=reason,
                parent_version=old_version,
                metadata=metadata or {},
            )
            self._current = new_snapshot
            self._condition.notify_all()
            return new_snapshot

    def swap(
        self,
        new_snapshot: DynamicSnapshot,
    ) -> DynamicSnapshot:
        """
        Atomically swap to a pre-built snapshot.

        Args:
            new_snapshot: Pre-built snapshot to swap in.

        Returns:
            Old snapshot (before swap).
        """
        with self._condition:
            old = self._current
            new_snapshot.version = self._version_counter + 1
            new_snapshot.parent_version = old.version if old else None

            if old is not None:
                self._history.append(old)
                if len(self._history) > self._max_history:
                    self._history.pop(0)

            self._version_counter = new_snapshot.version
            self._current = new_snapshot
            self._condition.notify_all()
            return old

    def rollback_to(
        self,
        version: int,
    ) -> Optional[DynamicSnapshot]:
        """
        Rollback to a specific version.

        Args:
            version: Target version number.

        Returns:
            Restored snapshot or None if not found.
        """
        with self._condition:
            target = None
            for snap in reversed(self._history):
                if snap.version == version:
                    target = snap
                    break

            if target is None:
                # Check if current is the target
                if self._current and self._current.version == version:
                    return self._current
                return None

            self._version_counter += 1
            restored = DynamicSnapshot(
                values=copy.deepcopy(target.values),
                version=self._version_counter,
                environment=target.environment,
                sources_used=list(target.sources_used),
                operator=target.operator,
                reason=f"rollback from v{self._current.version} to v{version}",
                parent_version=self._current.version if self._current else None,
                metadata=copy.deepcopy(target.metadata),
            )

            if self._current is not None:
                self._history.append(self._current)
                if len(self._history) > self._max_history:
                    self._history.pop(0)

            self._current = restored
            self._condition.notify_all()
            return restored

    def wait_for_version(
        self,
        target_version: int,
        timeout: Optional[float] = None,
    ) -> bool:
        """
        Wait until a specific version is activated.

        Args:
            target_version: Version to wait for.
            timeout: Timeout in seconds.

        Returns:
            True if version was reached, False on timeout.
        """
        with self._condition:
            end_time = None
            if timeout is not None:
                end_time = datetime.utcnow().timestamp() + timeout

            while self._current is None or self._current.version < target_version:
                if end_time is not None:
                    remaining = max(0, end_time - datetime.utcnow().timestamp())
                    if remaining <= 0:
                        return False
                    self._condition.wait(timeout=remaining)
                else:
                    self._condition.wait()
            return True

    def get_history(
        self,
    ) -> List[DynamicSnapshot]:
        """Get snapshot history."""
        with self._lock:
            return list(self._history)

    def get_version(
        self,
        version: int,
    ) -> Optional[DynamicSnapshot]:
        """Get a specific version from history."""
        with self._lock:
            if self._current and self._current.version == version:
                return self._current
            for snap in reversed(self._history):
                if snap.version == version:
                    return snap
            return None

    def get_stats(
        self,
    ) -> Dict[str, Any]:
        """Get store statistics."""
        with self._lock:
            return {
                "current_version": self._version_counter,
                "has_snapshot": self._current is not None,
                "history_size": len(self._history),
                "max_history": self._max_history,
                "environment": self._current.environment if self._current else None,
            }
