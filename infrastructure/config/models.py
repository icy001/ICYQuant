"""
Configuration data models.

Defines the core data structures for the
configuration platform, including individual
configuration items, configuration snapshots,
and validation results.

Design Principles:
- ConfigurationItem: A single key-value pair with metadata
- ConfigurationSnapshot: Immutable, atomic configuration view
- ValidationResult: Validation outcome with errors list
- Snapshot follows Immutable Snapshot pattern:
    Business threads read a complete, unmodifiable snapshot.
    Updates create a new snapshot and perform atomic switch,
    avoiding concurrent read/write issues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .constants import ConfigSource


@dataclass
class ConfigurationItem:
    """
    A single configuration item.

    Represents one key-value pair in the
    configuration system, along with its
    source, version, and metadata.

    Attributes:
        key: Configuration key (e.g., "server.port").
        value: Configuration value.
        source: Where the value came from.
        version: Version number for tracking changes.
        readonly: Whether the value cannot be modified.
        metadata: Additional metadata.
    """

    key: str
    value: Any
    source: str = ConfigSource.DEFAULT.value
    version: int = 1
    readonly: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def with_value(
        self,
        value: Any,
    ) -> ConfigurationItem:
        """
        Create a new item with updated value.

        Returns a new instance to maintain
        immutability of the original item.

        Args:
            value: New value.

        Returns:
            New ConfigurationItem instance.
        """

        return ConfigurationItem(
            key=self.key,
            value=value,
            source=self.source,
            version=self.version + 1,
            readonly=self.readonly,
            metadata=self.metadata.copy(),
        )

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """Convert to dictionary."""

        return {
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "version": self.version,
            "readonly": self.readonly,
            "metadata": self.metadata,
        }


@dataclass
class ConfigurationSnapshot:
    """
    Immutable configuration snapshot.

    Represents a complete, unmodifiable view
    of all configuration items at a point in time.

    This implements the Immutable Configuration
    Snapshot pattern: business threads read
    this snapshot; when configuration updates,
    a new snapshot is created and atomically
    swapped in, avoiding concurrent read/write
    issues.

    Benefits:
    - No locks needed for reads
    - Atomic configuration switching
    - Easy rollback to previous version
    - Version tracking for audit
    - Thread-safe by design

    Attributes:
        items: All configuration items.
        version: Snapshot version number.
        environment: Deployment environment.
        created_at: Snapshot creation timestamp.
        source: Primary source of this snapshot.
    """

    items: Dict[str, ConfigurationItem] = field(default_factory=dict)
    version: int = 1
    environment: str = "development"
    created_at: datetime = field(default_factory=datetime.utcnow)
    source: str = ConfigSource.DEFAULT.value

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Get a configuration value by key.

        Args:
            key: Configuration key.
            default: Default value if not found.

        Returns:
            Configuration value or default.
        """

        item = self.items.get(key)
        if item is None:
            return default
        return item.value

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
            value_type: Expected type (int, str, bool, etc.).
            default: Default value if not found or type mismatch.

        Returns:
            Typed configuration value.
        """

        value = self.get(key, default)
        if value is None:
            return default
        try:
            if value_type is bool:
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "yes")
                return bool(value)
            return value_type(value)
        except (TypeError, ValueError):
            return default

    def get_item(
        self,
        key: str,
    ) -> Optional[ConfigurationItem]:
        """Get a configuration item by key."""

        return self.items.get(key)

    def keys(
        self,
    ) -> List[str]:
        """Get all configuration keys."""

        return list(self.items.keys())

    def contains(
        self,
        key: str,
    ) -> bool:
        """Check if a key exists."""

        return key in self.items

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """Convert to dictionary."""

        return {
            key: item.to_dict()
            for key, item in self.items.items()
        }

    def to_flat_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Convert to flat key-value dictionary.

        Returns only the key-value pairs,
        without metadata.
        """

        return {
            key: item.value
            for key, item in self.items.items()
        }

    def merge(
        self,
        other: ConfigurationSnapshot,
    ) -> ConfigurationSnapshot:
        """
        Merge another snapshot into this one.

        Creates a new snapshot with items from
        both snapshots. Items from 'other' take
        precedence (higher priority).

        Args:
            other: Snapshot to merge.

        Returns:
            New merged snapshot.
        """

        merged_items = dict(self.items)
        for key, item in other.items.items():
            existing = merged_items.get(key)
            if existing is None or (
                ConfigSource(item.source).priority
                >= ConfigSource(existing.source).priority
            ):
                merged_items[key] = item

        return ConfigurationSnapshot(
            items=merged_items,
            version=max(self.version, other.version) + 1,
            environment=other.environment,
            created_at=datetime.utcnow(),
            source=other.source,
        )


@dataclass
class ValidationResult:
    """
    Configuration validation result.

    Attributes:
        valid: Whether validation passed.
        errors: List of validation errors.
        warnings: List of validation warnings.
    """

    valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(
        self,
        error: str,
    ) -> None:
        """Add an error and mark as invalid."""

        self.errors.append(error)
        self.valid = False

    def add_warning(
        self,
        warning: str,
    ) -> None:
        """Add a warning (does not affect validity)."""

        self.warnings.append(warning)

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """Convert to dictionary."""

        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }
