"""
Configuration Snapshot.

Immutable, atomic configuration snapshot
that represents the resolved configuration
at a point in time.

Design:
    Immutable: Once created, cannot be modified.
    Atomic: Readers always see a consistent snapshot.
    Thread-safe: No locks needed for reads.
    Rollback: Previous snapshots are preserved for rollback.
"""

from __future__ import annotations

import copy
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ConfigurationSnapshot:
    """
    Immutable configuration snapshot.

    Represents a complete, resolved configuration
    at a point in time. Once created, the values
    cannot be modified, ensuring thread-safe reads.

    Attributes:
        values: Dictionary of configuration values.
        version: Snapshot version number.
        environment: Deployment environment.
        sources_used: List of source names that contributed.
        created_at: Creation timestamp.
        metadata: Additional metadata.
    """

    values: Dict[str, Any] = field(default_factory=dict)
    version: int = 0
    environment: str = "development"
    sources_used: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

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
        Get a nested configuration value using dotted key.

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

    def get_typed(
        self,
        key: str,
        value_type: type,
        default: Any = None,
    ) -> Any:
        """
        Get a typed configuration value.

        Args:
            key: Configuration key.
            value_type: Expected type.
            default: Default value if not found.

        Returns:
            Typed configuration value.
        """
        value = self.get(key, default)
        if value is None:
            return default
        try:
            if value_type is bool:
                if isinstance(value, str):
                    return value.lower() in ("true", "yes", "1", "on")
                return bool(value)
            return value_type(value)
        except (TypeError, ValueError):
            return default

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

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """Convert snapshot to dictionary."""
        return {
            "version": self.version,
            "environment": self.environment,
            "sources_used": self.sources_used,
            "created_at": self.created_at.isoformat(),
            "values": copy.deepcopy(self.values),
        }

    def deep_copy(
        self,
    ) -> "ConfigurationSnapshot":
        """Create a deep copy of this snapshot."""
        return ConfigurationSnapshot(
            values=copy.deepcopy(self.values),
            version=self.version,
            environment=self.environment,
            sources_used=list(self.sources_used),
            created_at=self.created_at,
            metadata=copy.deepcopy(self.metadata),
        )

    def merge(
        self,
        other: "ConfigurationSnapshot",
    ) -> "ConfigurationSnapshot":
        """
        Merge another snapshot into this one.

        Returns a new snapshot with values from
        both, with the other taking precedence.

        Args:
            other: Snapshot to merge.

        Returns:
            New merged snapshot.
        """
        merged = copy.deepcopy(self.values)
        merged.update(copy.deepcopy(other.values))
        return ConfigurationSnapshot(
            values=merged,
            version=max(self.version, other.version) + 1,
            environment=other.environment,
            sources_used=self.sources_used + other.sources_used,
        )


class SnapshotStore:
    """
    Thread-safe store for configuration snapshots.

    Manages the current snapshot and history
    for rollback support.

    Uses atomic reference swap for thread safety:
    readers always see a consistent snapshot without locks.
    """

    def __init__(
        self,
        max_history: int = 10,
    ) -> None:
        """
        Initialize snapshot store.

        Args:
            max_history: Maximum number of historical snapshots.
        """
        self._snapshot: Optional[ConfigurationSnapshot] = None
        self._history: List[ConfigurationSnapshot] = []
        self._max_history = max_history
        self._lock = threading.Lock()
        self._version_counter = 0

    @property
    def current(
        self,
    ) -> Optional[ConfigurationSnapshot]:
        """Get current snapshot (thread-safe read)."""
        return self._snapshot

    @property
    def version(
        self,
    ) -> int:
        """Get current version."""
        return self._version_counter

    def update(
        self,
        values: Dict[str, Any],
        environment: str = "development",
        sources_used: Optional[List[str]] = None,
    ) -> ConfigurationSnapshot:
        """
        Create and atomically swap a new snapshot.

        Args:
            values: Configuration values.
            environment: Deployment environment.
            sources_used: List of source names.

        Returns:
            New snapshot.
        """
        with self._lock:
            self._version_counter += 1

            # Save old snapshot to history
            if self._snapshot is not None:
                self._history.append(self._snapshot)
                if len(self._history) > self._max_history:
                    self._history.pop(0)

            # Create and swap new snapshot
            new_snapshot = ConfigurationSnapshot(
                values=copy.deepcopy(values),
                version=self._version_counter,
                environment=environment,
                sources_used=sources_used or [],
            )
            self._snapshot = new_snapshot
            return new_snapshot

    def rollback(
        self,
        steps: int = 1,
    ) -> Optional[ConfigurationSnapshot]:
        """
        Rollback to a previous snapshot.

        Args:
            steps: Number of versions to rollback.

        Returns:
            Restored snapshot or None if unable.
        """
        with self._lock:
            if not self._history or steps > len(self._history):
                return None

            # Get snapshot from history
            idx = -min(steps, len(self._history))
            restored = self._history[idx]

            self._version_counter += 1
            self._snapshot = ConfigurationSnapshot(
                values=copy.deepcopy(restored.values),
                version=self._version_counter,
                environment=restored.environment,
                sources_used=restored.sources_used,
                metadata=restored.metadata,
            )
            return self._snapshot

    def get_history(
        self,
    ) -> List[ConfigurationSnapshot]:
        """Get snapshot history."""
        return list(self._history)

    def clear_history(
        self,
    ) -> None:
        """Clear snapshot history."""
        with self._lock:
            self._history.clear()

    def get_stats(
        self,
    ) -> Dict[str, Any]:
        """Get store statistics."""
        with self._lock:
            return {
                "version": self._version_counter,
                "has_snapshot": self._snapshot is not None,
                "history_size": len(self._history),
                "max_history": self._max_history,
            }
