from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .manager import PluginManager
from .models import Plugin, PluginState
from .manifest import PluginManifest
from .context import PluginContext

logger = logging.getLogger(__name__)


class PluginService:
    """High-level service wrapping PluginManager.

    Provides a simpler API for external consumers
    (OMS, Risk Engine, Execution Engine, etc.).

    Usage::

        service = PluginService()
        await service.start()
        await service.install_manifest(manifest)
        plugin = service.get_plugin("broker.ibkr")
        await service.stop()
    """

    def __init__(self, manager: PluginManager | None = None) -> None:
        self._manager = manager or PluginManager()

    @property
    def manager(self) -> PluginManager:
        """Return the underlying PluginManager."""
        return self._manager

    async def start(self) -> None:
        """Initialize the plugin manager."""
        await self._manager.initialize()
        logger.info("Plugin service started.")

    async def shutdown(self) -> None:
        """Graceful shutdown: stop all plugins and clean up."""
        await self._manager.shutdown()
        logger.info("Plugin service shut down.")

    # ── Install / Remove ──────────────────────────────────────────

    async def install_manifest(self, manifest: PluginManifest) -> Plugin:
        """Install a plugin from a manifest."""
        return await self._manager.install(manifest)

    async def install_from_dict(self, data: dict) -> Plugin:
        """Install a plugin from a dictionary."""
        return await self._manager.install_from_dict(data)

    async def remove(self, plugin_id: str) -> Dict[str, Any]:
        """Remove (uninstall) a plugin."""
        return await self._manager.uninstall(plugin_id)

    # ── Load / Unload ────────────────────────────────────────────

    async def load_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Load a plugin."""
        return await self._manager.load(plugin_id)

    async def unload_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Unload a plugin."""
        return await self._manager.unload(plugin_id)

    # ── Start / Stop ──────────────────────────────────────────────

    async def start_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Start a plugin."""
        return await self._manager.start(plugin_id)

    async def stop_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Stop a plugin."""
        return await self._manager.stop(plugin_id)

    # ── Query ─────────────────────────────────────────────────────

    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """Get a plugin by ID."""
        return self._manager.get_plugin(plugin_id)

    def list_plugins(self, state: PluginState | None = None) -> List[Plugin]:
        """List plugins, optionally filtered by state."""
        return self._manager.list_plugins(state=state)

    def list_running(self) -> List[Plugin]:
        """List all running plugins."""
        return self._manager.list_plugins(state=PluginState.RUNNING)

    def list_failed(self) -> List[Plugin]:
        """List all failed plugins."""
        return self._manager.list_plugins(state=PluginState.FAILED)

    # ── Health / Diagnostics ──────────────────────────────────────

    async def health_check(self) -> Dict[str, Any]:
        """Run a full health check."""
        return await self._manager.health_check()

    def diagnostics(self, plugin_id: str = "") -> List[Dict[str, Any]]:
        """Get diagnostics for a plugin or all plugins."""
        return self._manager.get_diagnostics(plugin_id=plugin_id)

    def metrics(self) -> Dict[str, Any]:
        """Get a snapshot of all metrics."""
        return self._manager.get_metrics_snapshot()

    # ── Reload ────────────────────────────────────────────────────

    async def reload_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Reload a plugin."""
        return await self._manager.reload(plugin_id)

    async def reload_all(self) -> Dict[str, Any]:
        """Reload all running plugins."""
        return await self._manager.reload_all()

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics from all sub-systems."""
        return self._manager.get_stats()