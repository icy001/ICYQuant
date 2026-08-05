"""Version-based routing for service discovery.

Provides ``VersionRouter`` which filters instances by version
constraints and supports version aliases such as "stable" → "v2".
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from ..instance import ServiceInstance
from .context import ResolveContext

logger = logging.getLogger(__name__)

_SUPPORTED_VERSIONS = {"v1", "v2", "beta", "canary", "stable"}


class VersionRouter:
    """Routes service instances by version constraints.

    Supports exact version matching and version aliases.
    Built-in alias: "stable" → "v2".

    Usage::

        router = VersionRouter()
        router.add_version_alias("production", "v2")
        filtered = router.filter(instances, context)
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._aliases: Dict[str, str] = {"stable": "v2"}
        self._route_count = 0
        self._version_hits: Dict[str, int] = {}

    def filter(
        self,
        instances: List[ServiceInstance],
        context: Optional[ResolveContext] = None,
    ) -> List[ServiceInstance]:
        """Filter instances by version constraint.

        Uses the version from the context when available,
        resolving aliases as needed.

        Args:
            instances: Candidate instances.
            context: Optional resolution context.

        Returns:
            Filtered list of instances matching the version.
        """
        if not instances:
            return []

        requested = None
        if context is not None:
            requested = context.version

        if requested is None:
            return list(instances)

        resolved = self.resolve_version(requested)
        if resolved is None:
            resolved = requested

        with self._lock:
            self._route_count += 1
            self._version_hits[resolved] = (
                self._version_hits.get(resolved, 0) + 1
            )

        result: List[ServiceInstance] = []
        for instance in instances:
            if instance.version == resolved:
                result.append(instance)

        if not result:
            logger.debug(
                "No instances matched version '%s' (resolved: '%s').",
                requested,
                resolved,
            )
            return []

        return result

    def add_version_alias(self, alias: str, version: str) -> None:
        """Register a version alias.

        Args:
            alias: The alias name (e.g., "stable").
            version: The actual version string (e.g., "v2").
        """
        if not alias:
            raise ValueError("Alias cannot be empty.")
        if not version:
            raise ValueError("Version cannot be empty.")
        with self._lock:
            self._aliases[alias] = version
            logger.debug(
                "Version alias added: '%s' → '%s'", alias, version
            )

    def resolve_version(self, requested: str) -> Optional[str]:
        """Resolve a version string, following aliases.

        Args:
            requested: The requested version or alias.

        Returns:
            The resolved version string, or the original if no
            alias exists.
        """
        if requested is None:
            return None
        with self._lock:
            resolved = self._aliases.get(requested)
        if resolved is not None:
            return resolved
        return requested

    def get_versions(self) -> List[str]:
        """Return all known versions and aliases.

        Returns:
            A sorted list of version strings.
        """
        with self._lock:
            versions: set = set()
            versions.update(_SUPPORTED_VERSIONS)
            versions.update(self._aliases.keys())
            versions.update(self._aliases.values())
            for version in self._version_hits:
                versions.add(version)
            return sorted(versions)

    def get_stats(self) -> Dict[str, Any]:
        """Return version router statistics.

        Returns:
            A dictionary with routing counts and version usage.
        """
        with self._lock:
            return {
                "router": "VersionRouter",
                "route_count": self._route_count,
                "version_hits": dict(self._version_hits),
                "aliases": dict(self._aliases),
                "known_versions": self.get_versions(),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"VersionRouter(aliases={len(self._aliases)}, "
                f"routes={self._route_count})"
            )