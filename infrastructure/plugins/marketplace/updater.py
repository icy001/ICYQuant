"""Online update management for the plugin marketplace.

Provides :class:`MarketplaceUpdater` for checking, downloading,
and applying plugin updates from connected repositories.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from ..exceptions import PluginInstallError
from ..utils import compare_versions

from .resolver import MarketplaceResolver
from .installer import MarketplaceInstaller

logger = logging.getLogger(__name__)


class MarketplaceUpdater:
    """Manages online updates for installed plugins.

    Compares installed versions against available versions,
    downloads updates from repositories, and delegates
    installation to the :class:`MarketplaceInstaller`.

    Usage::

        updater = MarketplaceUpdater()
        updates = await updater.check_for_updates("my.plugin", "1.0.0")
        result = await updater.update_plugin("my.plugin", "2.0.0")
    """

    def __init__(
        self,
        resolver: Optional[MarketplaceResolver] = None,
        installer: Optional[MarketplaceInstaller] = None,
    ) -> None:
        self._resolver = resolver or MarketplaceResolver()
        self._installer = installer or MarketplaceInstaller()
        self._update_history: List[Dict[str, Any]] = []
        self._check_count: int = 0
        self._update_count: int = 0
        self._failure_count: int = 0

    async def check_for_updates(
        self,
        plugin_id: str,
        current_version: str,
    ) -> List[Dict[str, Any]]:
        """Check a plugin for available updates.

        Args:
            plugin_id: The plugin identifier to check.
            current_version: Currently installed version.

        Returns:
            A list of available update dictionaries, each with
            ``version``, ``channel``, and ``release_date`` keys.
            Empty if no updates are available.
        """
        self._check_count += 1
        try:
            all_versions = self._resolver.get_all_versions(plugin_id)
            updates: List[Dict[str, Any]] = []

            for ver in all_versions:
                if compare_versions(ver, current_version) > 0:
                    updates.append(
                        {
                            "version": ver,
                            "channel": "stable",
                            "release_date": None,
                        }
                    )

            updates.sort(
                key=lambda x: x["version"],
                reverse=True,
            )

            logger.debug(
                "Found %d update(s) for '%s' (current=%s).",
                len(updates),
                plugin_id,
                current_version,
            )
            return updates
        except Exception as exc:
            logger.error(
                "Failed to check updates for '%s': %s",
                plugin_id,
                exc,
            )
            return []

    async def update_plugin(
        self,
        plugin_id: str,
        target_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a plugin to a target version.

        Args:
            plugin_id: The plugin identifier to update.
            target_version: Optional target version. Defaults to
                the latest available version.

        Returns:
            A dictionary with update result.
        """
        self._update_count += 1
        start_time = time.time()

        try:
            if target_version is None:
                target_version = self._resolver.get_latest_version(
                    plugin_id
                )
                if target_version is None:
                    raise PluginInstallError(
                        f"No version found for '{plugin_id}'."
                    )

            result = await self._installer.install_from_repository(
                plugin_id, target_version
            )

            elapsed = time.time() - start_time
            history_entry: Dict[str, Any] = {
                "plugin_id": plugin_id,
                "target_version": target_version,
                "timestamp": time.time(),
                "duration_seconds": elapsed,
                "success": True,
            }
            self._update_history.append(history_entry)

            logger.info(
                "Updated plugin '%s' to version '%s' in %.2fs.",
                plugin_id,
                target_version,
                elapsed,
            )
            return {
                "success": True,
                "plugin_id": plugin_id,
                "version": target_version,
                "duration_seconds": elapsed,
                "message": f"Plugin updated to {target_version}.",
            }
        except Exception as exc:
            self._failure_count += 1
            elapsed = time.time() - start_time
            self._update_history.append(
                {
                    "plugin_id": plugin_id,
                    "target_version": target_version,
                    "timestamp": time.time(),
                    "duration_seconds": elapsed,
                    "success": False,
                    "error": str(exc),
                }
            )
            logger.error(
                "Failed to update plugin '%s': %s", plugin_id, exc
            )
            raise PluginInstallError(
                f"Failed to update plugin '{plugin_id}': {exc}"
            ) from exc

    async def update_all(self) -> Dict[str, Any]:
        """Update all outdated plugins.

        Checks each installed plugin and applies available updates.

        Returns:
            A dictionary with ``updated``, ``failed``, and
            ``total`` counts.
        """
        logger.info("Starting bulk update of all plugins.")
        updated: List[str] = []
        failed: List[Dict[str, str]] = []

        try:
            from ..registry import PluginRegistry

            registry = PluginRegistry()
            plugins = registry.get_all()

            for plugin in plugins:
                pid = getattr(plugin, "id", "")
                ver = getattr(plugin, "version", "")

                try:
                    updates = await self.check_for_updates(pid, ver)
                    if updates:
                        target = updates[0]["version"]
                        result = await self.update_plugin(pid, target)
                        if result.get("success"):
                            updated.append(pid)
                        else:
                            failed.append(
                                {
                                    "plugin_id": pid,
                                    "error": result.get(
                                        "message", "Unknown"
                                    ),
                                }
                            )
                except Exception as exc:
                    failed.append(
                        {"plugin_id": pid, "error": str(exc)}
                    )

        except Exception as exc:
            logger.error("Bulk update error: %s", exc)

        logger.info(
            "Bulk update complete: %d updated, %d failed.",
            len(updated),
            len(failed),
        )
        return {
            "updated": updated,
            "failed": failed,
            "total": len(updated) + len(failed),
        }

    def get_update_history(
        self, plugin_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get update history, optionally filtered by plugin.

        Args:
            plugin_id: Optional plugin ID filter.

        Returns:
            A list of update history entries.
        """
        if plugin_id:
            return [
                h
                for h in self._update_history
                if h.get("plugin_id") == plugin_id
            ]
        return list(self._update_history)

    def get_stats(self) -> Dict[str, Any]:
        """Return updater statistics.

        Returns:
            Dictionary with check and update counts.
        """
        return {
            "check_count": self._check_count,
            "update_count": self._update_count,
            "failure_count": self._failure_count,
            "history_entries": len(self._update_history),
        }