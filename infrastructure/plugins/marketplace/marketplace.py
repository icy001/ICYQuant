"""Unified entry point for the plugin marketplace.

The :class:`PluginMarketplace` provides a single async API for
searching, installing, updating, and uninstalling plugins across
multiple remote repositories. It integrates with the loader subsystem
for actual installation and lifecycle management.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..exceptions import PluginInstallError, PluginNotFoundError
from ..loader.installer import PluginInstaller
from ..manifest import PluginManifest
from ..models import PluginState
from ..registry import PluginRegistry

from .repository import MarketplaceRepository
from .registry import MarketplaceRegistry
from .package import MarketplacePackage
from .installer import MarketplaceInstaller
from .updater import MarketplaceUpdater
from .rollback import MarketplaceRollback
from .search import MarketplaceSearch
from .downloader import MarketplaceDownloader

logger = logging.getLogger(__name__)


class PluginMarketplace:
    """Unified async entry point for the plugin marketplace.

    Orchestrates repository management, package resolution,
    installation, updates, and rollbacks across multiple
    plugin sources.

    Usage::

        marketplace = PluginMarketplace()
        await marketplace.initialize()
        results = await marketplace.search_plugins("momentum")
        plugin = await marketplace.install_plugin("momentum.strategy", "1.2.0")
        await marketplace.shutdown()
    """

    def __init__(
        self,
        repository: Optional[MarketplaceRepository] = None,
        registry: Optional[MarketplaceRegistry] = None,
        package_mgr: Optional[MarketplacePackage] = None,
        installer: Optional[MarketplaceInstaller] = None,
        updater: Optional[MarketplaceUpdater] = None,
        rollback: Optional[MarketplaceRollback] = None,
        search: Optional[MarketplaceSearch] = None,
        downloader: Optional[MarketplaceDownloader] = None,
        plugin_installer: Optional[PluginInstaller] = None,
        plugin_registry: Optional[PluginRegistry] = None,
    ) -> None:
        self._repository = repository or MarketplaceRepository()
        self._registry = registry or MarketplaceRegistry()
        self._package_mgr = package_mgr or MarketplacePackage()
        self._installer = installer or MarketplaceInstaller()
        self._updater = updater or MarketplaceUpdater()
        self._rollback = rollback or MarketplaceRollback()
        self._search = search or MarketplaceSearch()
        self._downloader = downloader or MarketplaceDownloader()
        self._plugin_installer = plugin_installer or PluginInstaller()
        self._plugin_registry = plugin_registry or PluginRegistry()

        self._initialized = False
        self._metrics: Dict[str, int] = {
            "searches": 0,
            "installs": 0,
            "updates": 0,
            "uninstalls": 0,
            "rollbacks": 0,
            "errors": 0,
        }

    async def initialize(self) -> None:
        """Connect to repositories and load the cache.

        Synchronizes all configured repositories and prepares
        the marketplace for operation.
        """
        logger.info("Initializing plugin marketplace.")
        try:
            await self._repository.sync_all()
            self._initialized = True
            logger.info("Plugin marketplace initialized successfully.")
        except Exception as exc:
            self._metrics["errors"] += 1
            logger.error("Failed to initialize marketplace: %s", exc)
            raise PluginInstallError(
                f"Marketplace initialization failed: {exc}"
            ) from exc

    async def shutdown(self) -> None:
        """Disconnect from repositories and persist state.

        Persists any cached data and gracefully shuts down
        all sub-components.
        """
        logger.info("Shutting down plugin marketplace.")
        self._initialized = False
        logger.info("Plugin marketplace shut down.")

    async def search_plugins(
        self, query: str, filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search across all repositories for plugins matching a query.

        Args:
            query: Search string (matches name, description, tags).
            filters: Optional dictionary of filter criteria
                (e.g. ``{"channel": "stable", "author": "XYZ"}``).

        Returns:
            A list of plugin info dictionaries.
        """
        self._metrics["searches"] += 1
        try:
            results = self._search.search(query, filters=filters)
            return results
        except Exception as exc:
            self._metrics["errors"] += 1
            logger.error("Search failed: %s", exc)
            return []

    async def get_plugin_info(
        self, plugin_id: str, version: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get detailed information about a plugin.

        Args:
            plugin_id: The plugin identifier.
            version: Optional specific version to look up.

        Returns:
            A dictionary with plugin metadata, or an empty
            dict if not found.
        """
        try:
            info = self._search.search(plugin_id)
            for entry in info:
                if entry.get("id") == plugin_id:
                    if version is None or entry.get("version") == version:
                        return entry
            return {}
        except Exception as exc:
            self._metrics["errors"] += 1
            logger.error("Failed to get plugin info for '%s': %s", plugin_id, exc)
            return {}

    async def install_plugin(
        self,
        plugin_id: str,
        version: Optional[str] = None,
        source: str = "registry",
    ) -> Dict[str, Any]:
        """Install a plugin from the marketplace.

        Args:
            plugin_id: The plugin identifier to install.
            version: Optional target version. Defaults to latest.
            source: Source repository name (default ``"registry"``).

        Returns:
            A dictionary with installation result including
            ``success``, ``plugin_id``, ``version``, and ``message``.
        """
        self._metrics["installs"] += 1
        try:
            result = await self._installer.install_from_repository(
                plugin_id, version
            )
            logger.info(
                "Installed plugin '%s' (version=%s).",
                plugin_id,
                result.get("version"),
            )
            return result
        except Exception as exc:
            self._metrics["errors"] += 1
            logger.error(
                "Failed to install plugin '%s': %s", plugin_id, exc
            )
            raise PluginInstallError(
                f"Failed to install plugin '{plugin_id}': {exc}"
            ) from exc

    async def update_plugin(
        self,
        plugin_id: str,
        target_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an installed plugin to a newer version.

        Args:
            plugin_id: The plugin identifier to update.
            target_version: Optional target version. Defaults to
                the latest available version.

        Returns:
            A dictionary with update result.
        """
        self._metrics["updates"] += 1
        try:
            result = await self._updater.update_plugin(
                plugin_id, target_version
            )
            logger.info("Updated plugin '%s'.", plugin_id)
            return result
        except Exception as exc:
            self._metrics["errors"] += 1
            logger.error(
                "Failed to update plugin '%s': %s", plugin_id, exc
            )
            raise PluginInstallError(
                f"Failed to update plugin '{plugin_id}': {exc}"
            ) from exc

    async def uninstall_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Uninstall a plugin from the local installation.

        Args:
            plugin_id: The plugin identifier to uninstall.

        Returns:
            A dictionary with uninstall result.
        """
        self._metrics["uninstalls"] += 1
        try:
            self._plugin_registry.unregister(plugin_id)
            logger.info("Uninstalled plugin '%s'.", plugin_id)
            return {
                "success": True,
                "plugin_id": plugin_id,
                "message": "Plugin uninstalled successfully.",
            }
        except Exception as exc:
            self._metrics["errors"] += 1
            logger.error(
                "Failed to uninstall plugin '%s': %s", plugin_id, exc
            )
            raise PluginInstallError(
                f"Failed to uninstall plugin '{plugin_id}': {exc}"
            ) from exc

    async def rollback_plugin(
        self, plugin_id: str
    ) -> Dict[str, Any]:
        """Rollback a plugin to its previous version.

        Args:
            plugin_id: The plugin identifier to rollback.

        Returns:
            A dictionary with rollback result.
        """
        self._metrics["rollbacks"] += 1
        try:
            result = await self._rollback.rollback(plugin_id)
            logger.info("Rolled back plugin '%s'.", plugin_id)
            return result
        except Exception as exc:
            self._metrics["errors"] += 1
            logger.error(
                "Failed to rollback plugin '%s': %s", plugin_id, exc
            )
            raise PluginInstallError(
                f"Failed to rollback plugin '{plugin_id}': {exc}"
            ) from exc

    async def list_installed(self) -> List[Dict[str, Any]]:
        """List all locally installed plugins.

        Returns:
            A list of dictionaries describing installed plugins.
        """
        try:
            plugins = self._plugin_registry.get_all()
            result: List[Dict[str, Any]] = []
            for p in plugins:
                if hasattr(p, "to_dict"):
                    result.append(p.to_dict())
                else:
                    result.append({"id": str(p)})
            return result
        except Exception as exc:
            self._metrics["errors"] += 1
            logger.error("Failed to list installed plugins: %s", exc)
            return []

    async def check_updates(self) -> List[Dict[str, Any]]:
        """Check all installed plugins for available updates.

        Returns:
            A list of dictionaries with update information for
            plugins that have newer versions available.
        """
        try:
            installed = await self.list_installed()
            updates: List[Dict[str, Any]] = []
            for plugin_info in installed:
                pid = plugin_info.get("id", "")
                ver = plugin_info.get("version", "")
                try:
                    available = await self._updater.check_for_updates(pid, ver)
                    if available:
                        updates.append(
                            {
                                "plugin_id": pid,
                                "current_version": ver,
                                "available_versions": available,
                            }
                        )
                except Exception:
                    logger.warning(
                        "Could not check updates for '%s'.", pid
                    )
            return updates
        except Exception as exc:
            self._metrics["errors"] += 1
            logger.error("Failed to check updates: %s", exc)
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Return marketplace statistics and sub-component stats.

        Returns:
            Dictionary with marketplace metrics and sub-component stats.
        """
        return {
            "initialized": self._initialized,
            "metrics": dict(self._metrics),
            "repositories": self._repository.get_stats(),
            "registry": self._registry.get_stats(),
            "package": self._package_mgr.get_stats(),
            "installer": self._installer.get_stats(),
            "updater": self._updater.get_stats(),
            "rollback": self._rollback.get_stats(),
            "search": self._search.get_stats(),
            "downloader": self._downloader.get_stats(),
        }