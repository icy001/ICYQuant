from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from .exceptions import PluginError

logger = logging.getLogger(__name__)

_SEMVER_RE = re.compile(
    r"^(\d+)\.(\d+)\.(\d+)"
    r"(?:-([0-9A-Za-z.-]+))?"
    r"(?:\+([0-9A-Za-z.-]+))?$"
)


@dataclass
class PluginVersion:
    """Records a single version-related action for a plugin."""

    plugin_id: str
    version: str
    previous_version: Optional[str] = None
    action: str = "install"
    timestamp: datetime = None

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the version record to a dictionary.

        Returns:
            A dictionary with all version fields.
        """
        return {
            "plugin_id": self.plugin_id,
            "version": self.version,
            "previous_version": self.previous_version,
            "action": self.action,
            "timestamp": self.timestamp.isoformat(),
        }


class VersionManager:
    """Tracks install, upgrade, and rollback history for every
    plugin, with semantic version comparison and diff support.
    """

    def __init__(self) -> None:
        self._history: Dict[str, List[PluginVersion]] = {}
        self._current: Dict[str, str] = {}
        self._stats: Dict[str, int] = {
            "installs": 0,
            "upgrades": 0,
            "rollbacks": 0,
            "total_records": 0,
        }

    def record_version(
        self,
        plugin_id: str,
        version: str,
        action: str = "install",
    ) -> PluginVersion:
        """Record a version action for a plugin.

        Args:
            plugin_id: The plugin identifier.
            version: The target version string.
            action: The action performed (``install``, ``upgrade``,
                or ``rollback``).

        Returns:
            The new :class:`PluginVersion` record.

        Raises:
            PluginError: If the action is not recognized.
        """
        if action not in ("install", "upgrade", "rollback"):
            raise PluginError(
                f"Unknown action '{action}'. "
                "Expected: install, upgrade, rollback."
            )

        previous = self._current.get(plugin_id)

        record = PluginVersion(
            plugin_id=plugin_id,
            version=version,
            previous_version=previous,
            action=action,
            timestamp=datetime.utcnow(),
        )

        self._history.setdefault(plugin_id, []).append(record)
        self._current[plugin_id] = version
        self._stats["total_records"] += 1

        if action == "install":
            self._stats["installs"] += 1
        elif action == "upgrade":
            self._stats["upgrades"] += 1
        elif action == "rollback":
            self._stats["rollbacks"] += 1

        logger.info(
            "Recorded %s of '%s' v%s (prev=%s).",
            action,
            plugin_id,
            version,
            previous or "N/A",
        )
        return record

    def get_version_history(
        self, plugin_id: str
    ) -> List[PluginVersion]:
        """Return the full version history for a plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            List of :class:`PluginVersion` records, oldest first.
        """
        return list(self._history.get(plugin_id, []))

    def get_current_version(
        self, plugin_id: str
    ) -> Optional[str]:
        """Return the current version of a plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            The version string, or ``None`` if not installed.
        """
        return self._current.get(plugin_id)

    def get_previous_version(
        self, plugin_id: str
    ) -> Optional[str]:
        """Return the previous version of a plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            The previous version string, or ``None``.
        """
        history = self._history.get(plugin_id, [])
        if len(history) < 2:
            return None
        return history[-2].version

    def compare_versions(self, v1: str, v2: str) -> int:
        """Compare two semantic version strings.

        Args:
            v1: First version string.
            v2: Second version string.

        Returns:
            Negative if *v1* < *v2*, zero if equal, positive if
            *v1* > *v2*.

        Raises:
            PluginError: If either version string is invalid.
        """
        parts1 = self._parse_semver(v1)
        parts2 = self._parse_semver(v2)

        for a, b in zip(parts1, parts2):
            if a < b:
                return -1
            if a > b:
                return 1
        return 0

    def get_diff(
        self, v1: str, v2: str
    ) -> Dict[str, Any]:
        """Compute the semantic version difference between two
        versions.

        Args:
            v1: Source version.
            v2: Target version.

        Returns:
            Diff dictionary with ``major``, ``minor``, ``patch``,
            ``prerelease`` flags, and ``change_type``.
        """
        parts1 = self._parse_semver(v1)
        parts2 = self._parse_semver(v2)

        major_changed = parts2[0] != parts1[0]
        minor_changed = parts2[1] != parts1[1]
        patch_changed = parts2[2] != parts1[2]

        prerelease_changed = False
        pre1 = self._extract_prerelease(v1)
        pre2 = self._extract_prerelease(v2)
        if pre1 != pre2:
            prerelease_changed = True

        if major_changed:
            change_type = "major"
        elif minor_changed:
            change_type = "minor"
        elif patch_changed:
            change_type = "patch"
        else:
            change_type = "prerelease" if prerelease_changed else "none"

        return {
            "v1": v1,
            "v2": v2,
            "major_changed": major_changed,
            "minor_changed": minor_changed,
            "patch_changed": patch_changed,
            "prerelease_changed": prerelease_changed,
            "change_type": change_type,
        }

    async def rollback(
        self, plugin_id: str
    ) -> Dict[str, Any]:
        """Rollback a plugin to its previous version.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            Rollback result dictionary.

        Raises:
            PluginError: If the plugin has no previous version
                to rollback to.
        """
        history = self._history.get(plugin_id, [])
        if len(history) < 2:
            raise PluginError(
                f"Plugin '{plugin_id}' has no previous version "
                "to rollback to."
            )

        current = history[-1].version
        previous_record = history[-2]
        previous_version = previous_record.version

        self.record_version(
            plugin_id=plugin_id,
            version=previous_version,
            action="rollback",
        )

        logger.info(
            "Rolled back '%s' from v%s to v%s.",
            plugin_id,
            current,
            previous_version,
        )
        return {
            "plugin_id": plugin_id,
            "from_version": current,
            "to_version": previous_version,
            "success": True,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get version manager statistics.

        Returns:
            A dictionary with history and counter information.
        """
        return {
            "tracked_plugins": len(self._current),
            "current_versions": dict(self._current),
            "history_counts": {
                pid: len(records)
                for pid, records in self._history.items()
            },
            "stats": dict(self._stats),
        }

    @staticmethod
    def _parse_semver(
        version: str,
    ) -> tuple:
        """Parse a semantic version string into its numeric components.

        Args:
            version: A semantic version string (e.g. ``"1.2.3"``).

        Returns:
            A tuple of ``(major, minor, patch)`` integers.

        Raises:
            PluginError: If the version string is not valid.
        """
        match = _SEMVER_RE.match(version.strip())
        if not match:
            raise PluginError(
                f"Invalid semantic version: '{version}'."
            )
        return (
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        )

    @staticmethod
    def _extract_prerelease(
        version: str,
    ) -> Optional[str]:
        """Extract the prerelease suffix from a version string.

        Args:
            version: A semantic version string.

        Returns:
            The prerelease identifier, or ``None``.
        """
        match = _SEMVER_RE.match(version.strip())
        if match is None:
            return None
        return match.group(4)