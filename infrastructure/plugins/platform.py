from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .models import Plugin, PluginState
from .registry import PluginRegistry
from .loader.loader import PluginLoader
from .sandbox.sandbox import Sandbox
from .marketplace.marketplace import PluginMarketplace
from .lifecycle import PluginLifecycle
from .events import PluginEvent, PluginEventBus, PluginEventType
from .manager import PluginManager
from .runtime import PluginRuntime
from .runtime_context import RuntimeContext
from .exceptions import (
    PluginError,
    PluginInstallError,
    PluginNotFoundError,
    PluginStateError,
    PluginStopError,
)

logger = logging.getLogger(__name__)


class PluginPlatform:
    """Unified plugin platform integrating all sub-systems.

    Provides a single public API for plugin management, delegating
    to specialised sub-systems:

    - **PluginRegistry**: Plugin registration and state tracking.
    - **PluginLoader**: Plugin discovery, loading, and unloading.
    - **Sandbox**: Security isolation and resource enforcement.
    - **PluginMarketplace**: Remote plugin installation and updates.
    - **PluginLifecycle**: State-machine transitions with hooks.
    - **PluginRuntime**: Active plugin instance management.

    Architecture::

        PluginPlatform
              │
    ┌─────────┼─────────┬───────────┐
    │         │         │           │
  Registry  Loader  Sandbox  Marketplace
    │         │         │           │
    └─────────┼─────────┴───────────┘
              │
          Lifecycle
              │
           Runtime
    """

    def __init__(
        self,
        registry: Optional[PluginRegistry] = None,
        loader: Optional[PluginLoader] = None,
        sandbox: Optional[Sandbox] = None,
        marketplace: Optional[PluginMarketplace] = None,
        lifecycle: Optional[PluginLifecycle] = None,
        manager: Optional[PluginManager] = None,
        runtime: Optional[PluginRuntime] = None,
        event_bus: Optional[PluginEventBus] = None,
    ) -> None:
        self._registry = registry or PluginRegistry()
        self._loader = loader or PluginLoader()
        self._sandbox = sandbox or Sandbox()
        self._marketplace = marketplace or PluginMarketplace()
        self._lifecycle = lifecycle or PluginLifecycle()
        self._manager = manager or PluginManager()
        self._runtime = runtime or PluginRuntime(
            registry=self._registry,
            loader=self._loader,
            sandbox=self._sandbox,
            event_bus=event_bus,
        )
        self._event_bus = event_bus or PluginEventBus()

        self._initialized = False
        self._shutdown_started = False

    async def initialize(self) -> None:
        """Initialize all sub-systems in dependency order.

        Sequence: Marketplace → Manager → Runtime.
        """
        if self._initialized:
            logger.debug("Plugin platform is already initialized.")
            return

        logger.info("Initializing plugin platform.")

        try:
            await self._marketplace.initialize()
            logger.info("Marketplace initialized.")
        except Exception as e:
            logger.error("Marketplace initialization failed: %s", e)

        await self._manager.initialize()
        logger.info("Plugin manager initialized.")

        self._initialized = True
        logger.info("Plugin platform initialized successfully.")

    async def install(
        self, plugin_id: str, version: Optional[str] = None
    ) -> Dict[str, Any]:
        """Install a plugin from the marketplace.

        Args:
            plugin_id: The plugin identifier to install.
            version: Optional target version.

        Returns:
            Installation result dictionary.
        """
        if not self._initialized:
            raise PluginStateError(
                "Plugin platform is not initialized. Call initialize() first."
            )

        try:
            result = await self._marketplace.install_plugin(
                plugin_id, version
            )
            logger.info(
                "Installed plugin '%s' (version=%s).",
                plugin_id,
                result.get("version", "latest"),
            )
            return result
        except Exception as e:
            logger.error(
                "Failed to install plugin '%s': %s", plugin_id, e
            )
            raise PluginInstallError(
                f"Failed to install plugin '{plugin_id}': {e}"
            ) from e

    async def update(
        self, plugin_id: str, version: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an installed plugin to a newer version.

        Args:
            plugin_id: The plugin identifier to update.
            version: Optional target version.

        Returns:
            Update result dictionary.
        """
        if not self._initialized:
            raise PluginStateError(
                "Plugin platform is not initialized. Call initialize() first."
            )

        try:
            result = await self._marketplace.update_plugin(
                plugin_id, version
            )
            logger.info("Updated plugin '%s'.", plugin_id)
            return result
        except Exception as e:
            logger.error(
                "Failed to update plugin '%s': %s", plugin_id, e
            )
            raise PluginInstallError(
                f"Failed to update plugin '{plugin_id}': {e}"
            ) from e

    async def uninstall(self, plugin_id: str) -> Dict[str, Any]:
        """Uninstall a plugin completely.

        Args:
            plugin_id: The plugin identifier to uninstall.

        Returns:
            Uninstall result dictionary.
        """
        if not self._initialized:
            raise PluginStateError(
                "Plugin platform is not initialized. Call initialize() first."
            )

        plugin = self._registry.get_plugin(plugin_id)
        if plugin is None:
            raise PluginNotFoundError(
                f"Plugin '{plugin_id}' not found in registry."
            )

        try:
            if plugin.state == PluginState.RUNNING:
                await self.stop(plugin_id)

            result = await self._marketplace.uninstall_plugin(plugin_id)
            logger.info("Uninstalled plugin '%s'.", plugin_id)
            return result
        except Exception as e:
            logger.error(
                "Failed to uninstall plugin '%s': %s", plugin_id, e
            )
            raise PluginInstallError(
                f"Failed to uninstall plugin '{plugin_id}': {e}"
            ) from e

    async def reload(self, plugin_id: str) -> Dict[str, Any]:
        """Reload a plugin through the runtime.

        Args:
            plugin_id: The plugin identifier to reload.

        Returns:
            Reload result dictionary.
        """
        if not self._initialized:
            raise PluginStateError(
                "Plugin platform is not initialized. Call initialize() first."
            )

        return await self._runtime.reload_plugin(plugin_id)

    async def start(self, plugin_id: str) -> Dict[str, Any]:
        """Start a plugin via the runtime.

        Args:
            plugin_id: The plugin identifier to start.

        Returns:
            Start result dictionary.
        """
        if not self._initialized:
            raise PluginStateError(
                "Plugin platform is not initialized. Call initialize() first."
            )

        return await self._runtime.start_plugin(plugin_id)

    async def stop(self, plugin_id: str) -> Dict[str, Any]:
        """Stop a running plugin.

        Args:
            plugin_id: The plugin identifier to stop.

        Returns:
            Stop result dictionary.
        """
        if not self._initialized:
            raise PluginStateError(
                "Plugin platform is not initialized. Call initialize() first."
            )

        return await self._runtime.stop_plugin(plugin_id)

    async def shutdown(self) -> None:
        """Full platform shutdown: stop all plugins, shut down sub-systems."""
        if self._shutdown_started:
            return
        self._shutdown_started = True

        logger.info("Plugin platform shutting down.")

        try:
            active = self._runtime.get_active_plugins()
            for plugin_id in active:
                try:
                    await self._runtime.stop_plugin(plugin_id)
                except Exception as e:
                    logger.error(
                        "Error stopping '%s' during shutdown: %s",
                        plugin_id,
                        e,
                    )
        except Exception as e:
            logger.error("Error during runtime shutdown: %s", e)

        try:
            await self._sandbox.shutdown()
        except Exception as e:
            logger.error("Error during sandbox shutdown: %s", e)

        try:
            await self._manager.shutdown()
        except Exception as e:
            logger.error("Error during manager shutdown: %s", e)

        try:
            await self._marketplace.shutdown()
        except Exception as e:
            logger.error("Error during marketplace shutdown: %s", e)

        self._initialized = False
        logger.info("Plugin platform shut down.")

    def list_plugins(self) -> List[Dict[str, Any]]:
        """List all registered plugins.

        Returns:
            A list of plugin dictionaries.
        """
        plugins = self._registry.get_all()
        result: List[Dict[str, Any]] = []
        for plugin in plugins:
            if hasattr(plugin, "to_dict"):
                result.append(plugin.to_dict())
            else:
                result.append({"id": str(plugin)})
        return result

    def get_plugin(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """Get a plugin's data by identifier.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            Plugin data dictionary, or None if not found.
        """
        plugin = self._registry.get_plugin(plugin_id)
        if plugin is None:
            return None
        if hasattr(plugin, "to_dict"):
            return plugin.to_dict()
        return {"id": str(plugin)}

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive platform statistics.

        Returns:
            A dictionary with stats from all sub-systems.
        """
        return {
            "initialized": self._initialized,
            "shutdown_started": self._shutdown_started,
            "registry": self._registry.get_stats(),
            "loader": self._loader.get_stats(),
            "sandbox": self._sandbox.get_stats(),
            "marketplace": self._marketplace.get_stats(),
            "lifecycle": self._lifecycle.get_stats(),
            "runtime": self._runtime.get_runtime_stats(),
            "event_bus": self._event_bus.get_stats(),
            "manager": self._manager.get_stats(),
        }