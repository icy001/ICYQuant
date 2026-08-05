"""Repository management for the plugin marketplace.

Provides :class:`MarketplaceRepository` for managing multiple
plugin repositories with support for stable, beta, and dev
release channels.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MarketplaceRepository:
    """Manages plugin repositories and their indexes.

    Supports multiple release channels (``stable``, ``beta``,
    ``dev``) and provides methods to add, remove, list, and
    synchronize repositories.

    Each repository entry contains:

    - ``name``    : Unique repository identifier.
    - ``url``     : Remote URL or local path to the repository index.
    - ``channel`` : Release channel (``stable``, ``beta``, ``dev``).
    - ``enabled`` : Whether the repository is active.
    - ``last_sync``: Timestamp of the last successful sync.
    - ``package_count``: Number of packages in the repository.
    """

    def __init__(self) -> None:
        self._repositories: Dict[str, Dict[str, Any]] = {}
        self._default_channel: str = "stable"
        self._sync_count: int = 0
        self._sync_errors: int = 0

    def add_repository(
        self, name: str, url: str, channel: str = "stable"
    ) -> None:
        """Add a new repository.

        Args:
            name: Unique repository name.
            url: Remote URL or local path to the repository index.
            channel: Release channel (``stable``, ``beta``, ``dev``).

        Raises:
            ValueError: If the repository already exists.
        """
        if name in self._repositories:
            raise ValueError(
                f"Repository '{name}' already exists. "
                "Use remove_repository() first to re-add."
            )

        self._repositories[name] = {
            "name": name,
            "url": url,
            "channel": channel,
            "enabled": True,
            "last_sync": None,
            "package_count": 0,
        }
        logger.info(
            "Added repository '%s' (channel=%s, url=%s).",
            name,
            channel,
            url,
        )

    def remove_repository(self, name: str) -> None:
        """Remove a repository by name.

        Args:
            name: Repository name to remove.

        Raises:
            KeyError: If the repository is not found.
        """
        if name not in self._repositories:
            raise KeyError(f"Repository '{name}' not found.")
        del self._repositories[name]
        logger.info("Removed repository '%s'.", name)

    def get_repository(self, name: str) -> Optional[Dict[str, Any]]:
        """Get repository information by name.

        Args:
            name: Repository name.

        Returns:
            A dictionary with repository details, or ``None``
            if not found.
        """
        return self._repositories.get(name)

    def list_repositories(self) -> List[Dict[str, Any]]:
        """List all configured repositories.

        Returns:
            A list of repository detail dictionaries.
        """
        return list(self._repositories.values())

    async def fetch_index(self, name: str) -> List[Dict[str, Any]]:
        """Fetch the package index from a repository.

        In a real implementation this would make an HTTP request.
        For now it returns an empty list as a placeholder.

        Args:
            name: Repository name to fetch from.

        Returns:
            A list of package metadata dictionaries.
        """
        repo = self._repositories.get(name)
        if repo is None:
            raise KeyError(f"Repository '{name}' not found.")

        if not repo.get("enabled", True):
            logger.warning(
                "Repository '%s' is disabled; skipping fetch.", name
            )
            return []

        logger.info("Fetching index from repository '%s'.", name)
        repo["last_sync"] = time.time()
        return []

    async def sync_all(self) -> Dict[str, int]:
        """Synchronize all enabled repositories.

        Fetches the package index from each enabled repository
        and updates local caches.

        Returns:
            A dictionary with ``success`` and ``failed`` counts.
        """
        success = 0
        failed = 0
        for name in list(self._repositories.keys()):
            try:
                await self.fetch_index(name)
                success += 1
                self._sync_count += 1
            except Exception as exc:
                failed += 1
                self._sync_errors += 1
                logger.error(
                    "Failed to sync repository '%s': %s", name, exc
                )

        logger.info(
            "Sync complete: %d succeeded, %d failed.", success, failed
        )
        return {"success": success, "failed": failed}

    def set_default_channel(self, channel: str) -> None:
        """Set the default release channel.

        Args:
            channel: Channel name (``stable``, ``beta``, ``dev``).
        """
        self._default_channel = channel
        logger.info("Default channel set to '%s'.", channel)

    def get_stats(self) -> Dict[str, Any]:
        """Return repository statistics.

        Returns:
            Dictionary with repository counts and sync metrics.
        """
        return {
            "total_repositories": len(self._repositories),
            "enabled_repositories": sum(
                1
                for r in self._repositories.values()
                if r.get("enabled", True)
            ),
            "default_channel": self._default_channel,
            "sync_count": self._sync_count,
            "sync_errors": self._sync_errors,
            "channels": sorted(
                set(
                    r.get("channel", "stable")
                    for r in self._repositories.values()
                )
            ),
        }