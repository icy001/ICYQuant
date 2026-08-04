"""
Configuration version management.

Provides version tracking, checksum verification,
and rollback target identification for configuration
snapshots.
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
class ConfigurationVersion:
    """
    Configuration version metadata.

    Tracks version information for each configuration
    snapshot, enabling audit trails and rollback targeting.

    Attributes:
        version: Monotonically increasing version number.
        timestamp: When this version was created.
        checksum: SHA-256 checksum of configuration data.
        operator: Who triggered this version.
        reason: Reason for this change.
        source: Source of the configuration.
        parent_version: Previous version number.
        description: Human-readable description.
    """

    version: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    checksum: str = ""
    operator: str = "system"
    reason: str = ""
    source: str = "file"
    parent_version: Optional[int] = None
    description: str = ""

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "checksum": self.checksum,
            "operator": self.operator,
            "reason": self.reason,
            "source": self.source,
            "parent_version": self.parent_version,
            "description": self.description,
        }


class ConfigurationVersionManager:
    """
    Manages configuration version history.

    Provides version tracking, checksum verification,
    and rollback target lookup.

    Usage:
        version_mgr = ConfigurationVersionManager()

        # Record a new version
        version_mgr.record(
            version=5,
            config_data={"server.port": 8080},
            operator="admin",
            reason="port change",
        )

        # Find rollback target
        target = version_mgr.find_rollback_target(
            version=3,
        )

        # Verify checksum
        valid = version_mgr.verify_checksum(version=5, data={...})
    """

    def __init__(
        self,
        max_history: int = 100,
    ) -> None:
        """
        Initialize version manager.

        Args:
            max_history: Maximum version history entries.
        """
        self._versions: Dict[int, ConfigurationVersion] = {}
        self._max_history = max_history
        self._lock = threading.Lock()

    def record(
        self,
        version: int,
        config_data: Dict[str, Any],
        operator: str = "system",
        reason: str = "",
        source: str = "file",
        parent_version: Optional[int] = None,
        description: str = "",
    ) -> ConfigurationVersion:
        """
        Record a new configuration version.

        Args:
            version: Version number.
            config_data: Configuration data for checksum.
            operator: Who triggered this change.
            reason: Reason for the change.
            source: Source of the configuration.
            parent_version: Previous version.
            description: Human-readable description.

        Returns:
            ConfigurationVersion metadata.
        """
        checksum = self._calculate_checksum(config_data)

        version_meta = ConfigurationVersion(
            version=version,
            checksum=checksum,
            operator=operator,
            reason=reason,
            source=source,
            parent_version=parent_version,
            description=description,
        )

        with self._lock:
            self._versions[version] = version_meta

            # Trim history
            if len(self._versions) > self._max_history:
                oldest = min(self._versions.keys())
                del self._versions[oldest]

        return version_meta

    def get_version(
        self,
        version: int,
    ) -> Optional[ConfigurationVersion]:
        """
        Get version metadata.

        Args:
            version: Version number.

        Returns:
            ConfigurationVersion or None.
        """
        with self._lock:
            return self._versions.get(version)

    def find_rollback_target(
        self,
        version: int,
    ) -> Optional[ConfigurationVersion]:
        """
        Find a version for rollback.

        Args:
            version: Target version.

        Returns:
            ConfigurationVersion or None.
        """
        return self.get_version(version)

    def find_by_checksum(
        self,
        checksum: str,
    ) -> Optional[ConfigurationVersion]:
        """
        Find a version by checksum.

        Args:
            checksum: SHA-256 checksum.

        Returns:
            ConfigurationVersion or None.
        """
        with self._lock:
            for version_meta in self._versions.values():
                if version_meta.checksum == checksum:
                    return version_meta
        return None

    def verify_checksum(
        self,
        version: int,
        config_data: Dict[str, Any],
    ) -> bool:
        """
        Verify checksum for a specific version.

        Args:
            version: Version to verify.
            config_data: Current configuration data.

        Returns:
            True if checksum matches.
        """
        version_meta = self.get_version(version)
        if version_meta is None:
            return False

        actual_checksum = self._calculate_checksum(config_data)
        return version_meta.checksum == actual_checksum

    def get_history(
        self,
    ) -> List[ConfigurationVersion]:
        """Get full version history sorted by version."""
        with self._lock:
            return sorted(
                self._versions.values(),
                key=lambda v: v.version,
            )

    def get_latest(
        self,
    ) -> Optional[ConfigurationVersion]:
        """Get the latest version."""
        history = self.get_history()
        return history[-1] if history else None

    @property
    def version_count(
        self,
    ) -> int:
        """Get number of tracked versions."""
        with self._lock:
            return len(self._versions)

    def _calculate_checksum(
        self,
        config_data: Dict[str, Any],
    ) -> str:
        """Calculate SHA-256 checksum of configuration data."""
        normalized = json.dumps(
            self._sort_dict(config_data),
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
            k: ConfigurationVersionManager._sort_dict(v)
            if isinstance(v, dict) else v
            for k, v in sorted(d.items())
        }
