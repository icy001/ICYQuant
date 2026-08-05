"""Version compatibility checking for the plugin marketplace.

Provides :class:`MarketplaceCompatibility` for checking whether
plugin versions are compatible with the current API version and
other plugins.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..utils import compare_versions, parse_version

logger = logging.getLogger(__name__)


class MarketplaceCompatibility:
    """Checks version compatibility for plugins.

    Uses semantic version comparison utilities from
    :mod:`infrastructure.plugins.utils` to determine whether
    a plugin version satisfies constraints or is compatible
    with the current API level.

    Usage::

        compat = MarketplaceCompatibility()
        result = compat.check_compatibility("my.plugin", "1.0.0")
        versions = compat.get_compatible_versions("my.plugin", ">=1.0")
        ok = compat.is_compatible(">=1.0", "1.2.3")
    """

    def __init__(self) -> None:
        self._compatibility_check_count: int = 0
        self._version_cache: Dict[str, List[str]] = {}

    def check_compatibility(
        self,
        plugin_id: str,
        version: str,
        api_version: str = "v1",
    ) -> Dict[str, Any]:
        """Check whether a plugin version is compatible.

        Args:
            plugin_id: The plugin identifier.
            version: The plugin version string.
            api_version: Target API version (default ``"v1"``).

        Returns:
            A dictionary with ``compatible`` (bool), ``reason`` (str),
            and ``details`` (dict) keys.
        """
        self._compatibility_check_count += 1

        details: Dict[str, Any] = {
            "plugin_id": plugin_id,
            "version": version,
            "api_version": api_version,
        }

        compatible = True
        reason = ""

        parsed = parse_version(version)
        details["parsed_version"] = list(parsed)

        if not parsed or parsed == (0, 0, 0):
            compatible = False
            reason = f"Invalid version string: '{version}'"

        details["compatible"] = compatible
        details["reason"] = reason

        logger.debug(
            "Compatibility check for '%s' v%s: compatible=%s.",
            plugin_id,
            version,
            compatible,
        )
        return {
            "compatible": compatible,
            "reason": reason,
            "details": details,
        }

    def get_compatible_versions(
        self,
        plugin_id: str,
        constraint: Optional[str] = None,
    ) -> List[str]:
        """Get all versions of a plugin that satisfy a constraint.

        Args:
            plugin_id: The plugin identifier.
            constraint: Optional version constraint (e.g.
                ``">=1.0.0"``, ``"<2.0"``).

        Returns:
            A sorted list of compatible version strings.
        """
        versions = self._version_cache.get(plugin_id, [])
        if not versions:
            return []

        if constraint is None:
            return sorted(
                versions, key=lambda v: parse_version(v)
            )

        compatible: List[str] = []
        for ver in versions:
            if self.satisfies_constraint(ver, constraint):
                compatible.append(ver)

        return sorted(compatible, key=lambda v: parse_version(v))

    def is_compatible(
        self, required: str, available: str
    ) -> bool:
        """Check whether an available version satisfies a requirement.

        Supports operators: ``>=``, ``<=``, ``>``, ``<``, ``==``,
        ``!=``, ``~=``. A bare version string is treated as ``>=``.

        Args:
            required: Version constraint (e.g. ``">=1.0.0"``).
            available: Actual version string.

        Returns:
            ``True`` if the available version satisfies the constraint.
        """
        if not required or not available:
            return False

        constraint = required.strip()

        if constraint.startswith(">="):
            return compare_versions(available, constraint[2:].strip()) >= 0
        if constraint.startswith("<="):
            return compare_versions(available, constraint[2:].strip()) <= 0
        if constraint.startswith("!="):
            return compare_versions(available, constraint[2:].strip()) != 0
        if constraint.startswith("=="):
            return compare_versions(available, constraint[2:].strip()) == 0
        if constraint.startswith("~="):
            target = constraint[2:].strip()
            req_parts = parse_version(target)
            avail_parts = parse_version(available)
            if len(req_parts) < 2:
                return compare_versions(available, target) == 0
            prefix_len = len(req_parts) - 1
            if len(avail_parts) < prefix_len:
                return False
            return (
                avail_parts[:prefix_len] == req_parts[:prefix_len]
                and compare_versions(available, target) >= 0
            )
        if constraint.startswith(">"):
            return compare_versions(available, constraint[1:].strip()) > 0
        if constraint.startswith("<"):
            return compare_versions(available, constraint[1:].strip()) < 0

        return compare_versions(available, constraint) >= 0

    def get_min_version(
        self, plugin_id: str
    ) -> Optional[str]:
        """Get the minimum available version of a plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            The minimum version string, or ``None`` if no versions
            are known.
        """
        versions = self._version_cache.get(plugin_id, [])
        if not versions:
            return None
        return min(versions, key=lambda v: parse_version(v))

    def get_max_version(
        self, plugin_id: str
    ) -> Optional[str]:
        """Get the maximum available version of a plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            The maximum version string, or ``None`` if no versions
            are known.
        """
        versions = self._version_cache.get(plugin_id, [])
        if not versions:
            return None
        return max(versions, key=lambda v: parse_version(v))

    def get_stats(self) -> Dict[str, Any]:
        """Return compatibility checker statistics.

        Returns:
            Dictionary with check count and cached version info.
        """
        return {
            "compatibility_check_count": self._compatibility_check_count,
            "plugins_with_versions": len(self._version_cache),
            "total_cached_versions": sum(
                len(v) for v in self._version_cache.values()
            ),
        }