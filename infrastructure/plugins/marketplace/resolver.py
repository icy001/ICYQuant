"""Version resolver for the plugin marketplace.

Provides :class:`MarketplaceResolver` for semantic version
resolution with constraint matching, version discovery, and
best-version selection.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..utils import compare_versions, parse_version

logger = logging.getLogger(__name__)


class MarketplaceResolver:
    """Resolves plugin versions with constraint matching.

    Maintains a registry of known versions per plugin and provides
    methods to find the best matching version given constraints,
    channels, or specific requirements.

    Usage::

        resolver = MarketplaceResolver()
        resolver.register_versions("my.plugin", ["1.0.0", "1.1.0", "2.0.0"])
        version = resolver.resolve_version("my.plugin", [">=1.0", "<2.0"])
        latest = resolver.get_latest_version("my.plugin", "stable")
    """

    def __init__(self) -> None:
        self._versions: Dict[str, List[str]] = {}
        self._channel_versions: Dict[str, Dict[str, List[str]]] = {}
        self._resolve_count: int = 0

    def resolve_version(
        self,
        plugin_id: str,
        constraints: Optional[List[str]] = None,
    ) -> Optional[str]:
        """Resolve the best matching version for a plugin.

        Args:
            plugin_id: The plugin identifier.
            constraints: Optional list of version constraints
                (e.g. ``[">=1.0.0", "<2.0"]``).

        Returns:
            The best matching version string, or ``None`` if no
            version satisfies all constraints.
        """
        self._resolve_count += 1
        versions = self._versions.get(plugin_id, [])
        if not versions:
            return None

        if not constraints:
            return self.get_latest_version(plugin_id)

        candidates: List[str] = []
        for ver in versions:
            if all(
                self.satisfies_constraint(ver, c)
                for c in constraints
            ):
                candidates.append(ver)

        if not candidates:
            logger.debug(
                "No version of '%s' satisfies constraints: %s",
                plugin_id,
                constraints,
            )
            return None

        best = max(candidates, key=lambda v: parse_version(v))
        logger.debug(
            "Resolved '%s' to version '%s' (constraints=%s).",
            plugin_id,
            best,
            constraints,
        )
        return best

    def get_latest_version(
        self,
        plugin_id: str,
        channel: str = "stable",
    ) -> Optional[str]:
        """Get the latest version of a plugin from a channel.

        Args:
            plugin_id: The plugin identifier.
            channel: Release channel name (default ``"stable"``).

        Returns:
            The latest version string, or ``None`` if not found.
        """
        channel_map = self._channel_versions.get(plugin_id, {})
        versions = channel_map.get(channel)
        if versions is None:
            versions = self._versions.get(plugin_id, [])

        if not versions:
            return None

        return max(versions, key=lambda v: parse_version(v))

    def get_all_versions(
        self, plugin_id: str
    ) -> List[str]:
        """Get all known versions of a plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            A sorted list of version strings.
        """
        versions = self._versions.get(plugin_id, [])
        return sorted(versions, key=lambda v: parse_version(v))

    def find_best_version(
        self,
        plugin_id: str,
        required_version: Optional[str] = None,
    ) -> Optional[str]:
        """Find the best version of a plugin given requirements.

        Args:
            plugin_id: The plugin identifier.
            required_version: Optional required version constraint.

        Returns:
            The best matching version, or ``None`` if not found.
        """
        if required_version is not None:
            return self.resolve_version(
                plugin_id, [required_version]
            )
        return self.get_latest_version(plugin_id)

    def satisfies_constraint(
        self, version: str, constraint: str
    ) -> bool:
        """Check whether a version satisfies a constraint.

        Supports operators: ``>=``, ``<=``, ``>``, ``<``, ``==``,
        ``!=``, ``~=``. A bare version string is treated as ``>=``.

        Args:
            version: The version to check.
            constraint: The version constraint.

        Returns:
            ``True`` if the version satisfies the constraint.
        """
        if not version or not constraint:
            return False

        constraint = constraint.strip()

        if constraint.startswith(">="):
            return (
                compare_versions(version, constraint[2:].strip())
                >= 0
            )
        if constraint.startswith("<="):
            return (
                compare_versions(version, constraint[2:].strip())
                <= 0
            )
        if constraint.startswith("!="):
            return (
                compare_versions(version, constraint[2:].strip())
                != 0
            )
        if constraint.startswith("=="):
            return (
                compare_versions(version, constraint[2:].strip())
                == 0
            )
        if constraint.startswith("~="):
            target = constraint[2:].strip()
            req_parts = parse_version(target)
            avail_parts = parse_version(version)
            if len(req_parts) < 2:
                return compare_versions(version, target) == 0
            prefix_len = len(req_parts) - 1
            if len(avail_parts) < prefix_len:
                return False
            return (
                avail_parts[:prefix_len] == req_parts[:prefix_len]
                and compare_versions(version, target) >= 0
            )
        if constraint.startswith(">"):
            return (
                compare_versions(version, constraint[1:].strip()) > 0
            )
        if constraint.startswith("<"):
            return (
                compare_versions(version, constraint[1:].strip()) < 0
            )

        return compare_versions(version, constraint) >= 0

    def get_stats(self) -> Dict[str, Any]:
        """Return resolver statistics.

        Returns:
            Dictionary with resolution counts and known plugins.
        """
        return {
            "resolve_count": self._resolve_count,
            "plugins_with_versions": len(self._versions),
            "total_versions": sum(
                len(v) for v in self._versions.values()
            ),
        }

    def register_versions(
        self,
        plugin_id: str,
        versions: List[str],
        channel: str = "stable",
    ) -> None:
        """Register known versions for a plugin.

        Args:
            plugin_id: The plugin identifier.
            versions: List of version strings.
            channel: Channel these versions belong to.
        """
        existing = self._versions.setdefault(plugin_id, [])
        for v in versions:
            if v not in existing:
                existing.append(v)

        channel_map = self._channel_versions.setdefault(
            plugin_id, {}
        )
        channel_versions = channel_map.setdefault(channel, [])
        for v in versions:
            if v not in channel_versions:
                channel_versions.append(v)

        logger.debug(
            "Registered %d versions for '%s' (channel=%s).",
            len(versions),
            plugin_id,
            channel,
        )