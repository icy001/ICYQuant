"""
Configuration registry.

Manages configuration items and provides
immutable snapshots for thread-safe reads.

Implements the Immutable Configuration Snapshot
pattern: business threads read a complete,
unmodifiable snapshot; when configuration
updates, a new snapshot is created and
atomically swapped in.

Benefits:
- No locks needed for reads (atomic reference swap)
- Concurrent reads never block writes
- Atomic configuration switching
- Easy rollback to previous version
- Version tracking for audit
- Thread-safe by design

Usage:
    registry = ConfigurationRegistry()
    registry.set("server.port", 8080, source="file")
    registry.set("server.host", "0.0.0.0", source="file")

    # Get immutable snapshot (thread-safe read)
    snapshot = registry.get_snapshot()
    port = snapshot.get("server.port")  # 8080

    # Update creates new snapshot atomically
    registry.set("server.port", 9090, source="env")

    # Old snapshot unchanged
    old_port = snapshot.get("server.port")  # Still 8080

    # New snapshot reflects update
    new_snapshot = registry.get_snapshot()
    new_port = new_snapshot.get("server.port")  # 9090
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .constants import ConfigSource, DEFAULT_ENVIRONMENT
from .exceptions import ConfigNotFoundError, ConfigSnapshotError
from .models import ConfigurationItem, ConfigurationSnapshot


class ConfigurationRegistry:
    """
    Configuration registry with immutable snapshots.

    Stores configuration items and provides
    immutable snapshots for concurrent reads.

    Thread Safety:
    - Writes are protected by a lock
    - Reads return immutable snapshots
    - Snapshot switching is atomic (reference swap)

    Attributes:
        None (use methods to interact)
    """

    def __init__(
        self,
        environment: str = DEFAULT_ENVIRONMENT,
    ) -> None:
        """Initialize registry."""

        self._items: Dict[str, ConfigurationItem] = {}
        self._environment = environment
        self._lock = threading.Lock()

        # Snapshot management
        self._snapshot: ConfigurationSnapshot = ConfigurationSnapshot(
            environment=environment,
        )
        self._snapshot_lock = threading.Lock()
        self._snapshot_version = 0

        # History for rollback (keep last N snapshots)
        self._history: List[ConfigurationSnapshot] = []
        self._max_history = 10

    @property
    def environment(
        self,
    ) -> str:
        """Get environment."""
        return self._environment

    @property
    def snapshot_version(
        self,
    ) -> int:
        """Get current snapshot version."""
        return self._snapshot_version

    @property
    def item_count(
        self,
    ) -> int:
        """Get number of registered items."""

        with self._lock:
            return len(self._items)

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Get a configuration value.

        Reads from the current snapshot,
        which is thread-safe and immutable.

        Args:
            key: Configuration key.
            default: Default value if not found.

        Returns:
            Configuration value.
        """

        return self._snapshot.get(key, default)

    def get_typed(
        self,
        key: str,
        value_type: type,
        default: Any = None,
    ) -> Any:
        """Get a typed configuration value."""

        return self._snapshot.get_typed(key, value_type, default)

    def get_item(
        self,
        key: str,
    ) -> Optional[ConfigurationItem]:
        """Get a configuration item with metadata."""

        return self._snapshot.get_item(key)

    def set(
        self,
        key: str,
        value: Any,
        source: str = ConfigSource.FILE.value,
        readonly: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Set a configuration value.

        Updates the item and creates a new
        immutable snapshot atomically.

        Args:
            key: Configuration key.
            value: Configuration value.
            source: Value source.
            readonly: Whether value is read-only.
            metadata: Additional metadata.
        """

        with self._lock:
            existing = self._items.get(key)
            version = (existing.version + 1) if existing else 1

            item = ConfigurationItem(
                key=key,
                value=value,
                source=source,
                version=version,
                readonly=readonly,
                metadata=metadata or {},
            )
            self._items[key] = item

            self._rebuild_snapshot()

    def set_many(
        self,
        items: Dict[str, Any],
        source: str = ConfigSource.FILE.value,
    ) -> None:
        """
        Set multiple configuration values at once.

        Creates a single new snapshot for all
        changes, ensuring atomicity.

        Args:
            items: Dictionary of key-value pairs.
            source: Value source for all items.
        """

        with self._lock:
            for key, value in items.items():
                existing = self._items.get(key)
                version = (existing.version + 1) if existing else 1
                self._items[key] = ConfigurationItem(
                    key=key,
                    value=value,
                    source=source,
                    version=version,
                )
            self._rebuild_snapshot()

    def delete(
        self,
        key: str,
    ) -> bool:
        """
        Delete a configuration item.

        Returns:
            True if item was present.
        """

        with self._lock:
            if key not in self._items:
                return False
            del self._items[key]
            self._rebuild_snapshot()
            return True

    def exists(
        self,
        key: str,
    ) -> bool:
        """Check if a key exists."""

        return self._snapshot.contains(key)

    def keys(
        self,
    ) -> List[str]:
        """Get all configuration keys."""

        return self._snapshot.keys()

    def get_snapshot(
        self,
    ) -> ConfigurationSnapshot:
        """
        Get the current immutable snapshot.

        The returned snapshot is immutable and
        thread-safe. It will not reflect any
        future changes to the registry.

        Returns:
            Current configuration snapshot.
        """

        with self._snapshot_lock:
            return self._snapshot

    def rollback(
        self,
        steps: int = 1,
    ) -> bool:
        """
        Rollback to a previous snapshot.

        Args:
            steps: Number of versions to rollback.

        Returns:
            True if rollback succeeded.
        """

        with self._lock:
            if not self._history or steps > len(self._history):
                return False

            # Get snapshot from history
            idx = -min(steps, len(self._history))
            snapshot = self._history[idx]

            # Rebuild items from snapshot
            self._items = dict(snapshot.items)
            self._rebuild_snapshot(skip_history=True)
            return True

    def get_history(
        self,
    ) -> List[ConfigurationSnapshot]:
        """Get snapshot history for audit."""

        return list(self._history)

    def get_stats(
        self,
    ) -> Dict[str, Any]:
        """Get registry statistics."""

        with self._lock:
            return {
                "items": len(self._items),
                "version": self._snapshot_version,
                "environment": self._environment,
                "history_size": len(self._history),
                "sources": list({
                    item.source for item in self._items.values()
                }),
            }

    def _rebuild_snapshot(
        self,
        skip_history: bool = False,
    ) -> None:
        """
        Rebuild the immutable snapshot.

        Creates a new snapshot from current items
        and atomically swaps it in. The old
        snapshot is added to history.

        Args:
            skip_history: Whether to skip adding old snapshot to history.
        """

        with self._snapshot_lock:
            # Save old snapshot to history
            if not skip_history and self._snapshot_version > 0:
                self._history.append(self._snapshot)
                if len(self._history) > self._max_history:
                    self._history.pop(0)

            # Create new snapshot
            self._snapshot_version += 1
            self._snapshot = ConfigurationSnapshot(
                items=dict(self._items),
                version=self._snapshot_version,
                environment=self._environment,
                created_at=datetime.utcnow(),
            )

    def clear(
        self,
    ) -> None:
        """Clear all configuration items."""

        with self._lock:
            self._items.clear()
            self._rebuild_snapshot()

    def merge(
        self,
        other: ConfigurationSnapshot,
    ) -> None:
        """
        Merge a snapshot into the registry.

        Items from the snapshot are added to
        the registry, with source priority
        determining which values take precedence.

        Args:
            other: Snapshot to merge.
        """

        with self._lock:
            for key, item in other.items.items():
                existing = self._items.get(key)
                if existing is None:
                    self._items[key] = item
                else:
                    existing_source = ConfigSource(existing.source)
                    new_source = ConfigSource(item.source)
                    if new_source.priority >= existing_source.priority:
                        self._items[key] = item
            self._rebuild_snapshot()
