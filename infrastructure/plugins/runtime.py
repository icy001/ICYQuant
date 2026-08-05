from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from .models import Plugin, PluginState
from .registry import PluginRegistry
from .loader.loader import PluginLoader
from .sandbox.sandbox import Sandbox
from .events import PluginEvent, PluginEventBus, PluginEventType
from .runtime_context import RuntimeContext
from .exceptions import (
    PluginError,
    PluginLoadError,
    PluginNotFoundError,
    PluginStartError,
    PluginStateError,
    PluginStopError,
)

logger = logging.getLogger(__name__)


class PluginRuntime:
    """Plugin runtime with lazy activation, parallel loading, and isolation.

    Manages the execution lifecycle of active plugin instances, providing:

    - **Lazy Activation**: Plugins are activated on first use rather than
      eagerly at startup.
    - **Parallel Loading**: Independent plugins can be loaded concurrently
      via ``asyncio.gather``.
    - **Runtime Isolation**: Each plugin receives a :class:`RuntimeContext`
      that restricts its access to approved platform capabilities.
    - **Automatic Recovery**: Failed plugins can be restarted automatically
      or on demand.

    Architecture::

        PluginRuntime
              │
    ┌─────────┼─────────┐
    │         │         │
  Registry  Loader   Sandbox
    │         │         │
    └─────────┼─────────┘
              │
     Active Plugin Instances
    """

    def __init__(
        self,
        registry: Optional[PluginRegistry] = None,
        loader: Optional[PluginLoader] = None,
        sandbox: Optional[Sandbox] = None,
        event_bus: Optional[PluginEventBus] = None,
    ) -> None:
        self._registry = registry or PluginRegistry()
        self._loader = loader or PluginLoader()
        self._sandbox = sandbox or Sandbox()
        self._event_bus = event_bus or PluginEventBus()

        self._active_instances: Dict[str, Any] = {}
        self._runtime_contexts: Dict[str, RuntimeContext] = {}
        self._activation_lock = asyncio.Lock()
        self._stats: Dict[str, int] = {
            "starts": 0,
            "stops": 0,
            "reloads": 0,
            "activations": 0,
            "deactivations": 0,
            "recoveries": 0,
            "errors": 0,
        }

    async def start_plugin(
        self,
        plugin_id: str,
        context: Optional[RuntimeContext] = None,
    ) -> Dict[str, Any]:
        """Start a plugin, loading and initialising it.

        If the plugin is not yet loaded, the loader is invoked first.
        A :class:`RuntimeContext` is created automatically when not
        provided.

        Args:
            plugin_id: The plugin identifier to start.
            context: Optional pre-built runtime context.

        Returns:
            Result dictionary with ``success``, ``plugin_id``,
            and ``state`` keys.
        """
        plugin = self._registry.get_plugin(plugin_id)
        if plugin is None:
            raise PluginNotFoundError(
                f"Plugin '{plugin_id}' not found in registry."
            )

        if plugin.state == PluginState.RUNNING:
            return {
                "success": True,
                "plugin_id": plugin_id,
                "state": plugin.state.value,
                "message": "Plugin is already running.",
            }

        if context is None:
            context = self._build_runtime_context(plugin_id)

        try:
            sandbox_runtime = await self._sandbox.create_sandbox(
                plugin_id, config=self._get_sandbox_config(plugin)
            )
            logger.debug(
                "Sandbox created for '%s': %s", plugin_id, sandbox_runtime
            )
        except Exception as e:
            logger.warning(
                "Sandbox creation failed for '%s': %s", plugin_id, e
            )

        start_time = time.monotonic()
        try:
            if plugin.state in (PluginState.REGISTERED, PluginState.FAILED, PluginState.STOPPED):
                load_result = await self._loader.load(plugin_id, context=context)
                if not load_result.get("success"):
                    raise PluginLoadError(
                        f"Failed to load plugin '{plugin_id}'."
                    )
                plugin = self._registry.get_plugin(plugin_id)

            plugin.state = PluginState.RUNNING
            plugin.started_at = time.monotonic()
            self._active_instances[plugin_id] = plugin
            self._runtime_contexts[plugin_id] = context

            if plugin.state == PluginState.LOADED:
                instance = plugin.instance
                if instance is not None:
                    start_method = getattr(instance, "start", None)
                    if callable(start_method):
                        result = start_method()
                        if asyncio.iscoroutine(result):
                            await result
                    self._active_instances[plugin_id] = instance

            self._registry.update_state(plugin_id, PluginState.RUNNING)

            duration = time.monotonic() - start_time
            self._stats["starts"] += 1

            event = PluginEvent(
                event_type=PluginEventType.STARTED,
                plugin_id=plugin_id,
                data={"state": PluginState.RUNNING.value, "duration": duration},
            )
            await self._event_bus.publish(event)

            logger.info(
                "Started plugin '%s' in %.4fs.", plugin_id, duration
            )
            return {
                "success": True,
                "plugin_id": plugin_id,
                "state": PluginState.RUNNING.value,
                "duration_seconds": duration,
            }
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(
                "Failed to start plugin '%s': %s", plugin_id, e
            )
            raise PluginStartError(
                f"Failed to start plugin '{plugin_id}': {e}"
            ) from e

    async def stop_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Stop a running plugin and release its runtime resources.

        Args:
            plugin_id: The plugin identifier to stop.

        Returns:
            Result dictionary with ``success`` and ``plugin_id`` keys.
        """
        plugin = self._registry.get_plugin(plugin_id)
        if plugin is None:
            raise PluginNotFoundError(
                f"Plugin '{plugin_id}' not found in registry."
            )

        if plugin.state != PluginState.RUNNING:
            return {
                "success": True,
                "plugin_id": plugin_id,
                "message": "Plugin is not running.",
            }

        try:
            instance = self._active_instances.get(plugin_id)
            if instance is not None:
                stop_method = getattr(instance, "stop", None)
                if callable(stop_method):
                    result = stop_method()
                    if asyncio.iscoroutine(result):
                        await result

            self._active_instances.pop(plugin_id, None)
            self._runtime_contexts.pop(plugin_id, None)

            plugin.state = PluginState.STOPPED
            plugin.stopped_at = time.monotonic()
            self._registry.update_state(plugin_id, PluginState.STOPPED)

            try:
                await self._sandbox.destroy_sandbox(plugin_id)
            except Exception:
                logger.debug(
                    "Sandbox already destroyed for '%s'.", plugin_id
                )

            self._stats["stops"] += 1

            event = PluginEvent(
                event_type=PluginEventType.STOPPED,
                plugin_id=plugin_id,
                data={"state": PluginState.STOPPED.value},
            )
            await self._event_bus.publish(event)

            logger.info("Stopped plugin '%s'.", plugin_id)
            return {
                "success": True,
                "plugin_id": plugin_id,
                "state": PluginState.STOPPED.value,
            }
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(
                "Failed to stop plugin '%s': %s", plugin_id, e
            )
            raise PluginStopError(
                f"Failed to stop plugin '{plugin_id}': {e}"
            ) from e

    async def reload_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Reload a plugin: stop, unload, then start again.

        Args:
            plugin_id: The plugin identifier to reload.

        Returns:
            Result dictionary with ``success`` and duration keys.
        """
        plugin = self._registry.get_plugin(plugin_id)
        if plugin is None:
            raise PluginNotFoundError(
                f"Plugin '{plugin_id}' not found in registry."
            )

        was_running = plugin.state == PluginState.RUNNING
        reload_start = time.monotonic()

        try:
            if was_running:
                await self.stop_plugin(plugin_id)

            if plugin.state != PluginState.UNINSTALLED:
                await self._loader.unload(plugin_id)

            context = self._build_runtime_context(plugin_id)
            load_result = await self._loader.load(plugin_id, context=context)
            if not load_result.get("success"):
                raise PluginLoadError(
                    f"Failed to reload plugin '{plugin_id}': load failed."
                )

            if was_running:
                await self.start_plugin(plugin_id, context=context)

            duration = time.monotonic() - reload_start
            self._stats["reloads"] += 1

            event = PluginEvent(
                event_type=PluginEventType.RELOADED,
                plugin_id=plugin_id,
                data={"duration": duration},
            )
            await self._event_bus.publish(event)

            logger.info(
                "Reloaded plugin '%s' in %.4fs.", plugin_id, duration
            )
            return {
                "success": True,
                "plugin_id": plugin_id,
                "duration_seconds": duration,
            }
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(
                "Failed to reload plugin '%s': %s", plugin_id, e
            )
            raise PluginError(
                f"Failed to reload plugin '{plugin_id}': {e}"
            ) from e

    async def activate_plugin(
        self, plugin_id: str
    ) -> Dict[str, Any]:
        """Lazily activate a plugin on first access.

        Activation transitions the plugin from LOADED to RUNNING
        without a full stop/start cycle.

        Args:
            plugin_id: The plugin identifier to activate.

        Returns:
            Result dictionary with ``success`` and state keys.
        """
        async with self._activation_lock:
            plugin = self._registry.get_plugin(plugin_id)
            if plugin is None:
                raise PluginNotFoundError(
                    f"Plugin '{plugin_id}' not found in registry."
                )

            if plugin.state == PluginState.RUNNING:
                return {
                    "success": True,
                    "plugin_id": plugin_id,
                    "state": plugin.state.value,
                    "message": "Plugin is already active.",
                }

            if plugin.state not in (PluginState.LOADED, PluginState.STOPPED, PluginState.FAILED):
                raise PluginStateError(
                    f"Cannot activate plugin '{plugin_id}' from state "
                    f"'{plugin.state.value}'."
                )

            context = self._runtime_contexts.get(plugin_id)
            if context is None:
                context = self._build_runtime_context(plugin_id)
                self._runtime_contexts[plugin_id] = context

            try:
                instance = plugin.instance
                if instance is None:
                    load_result = await self._loader.load(
                        plugin_id, context=context
                    )
                    if not load_result.get("success"):
                        raise PluginLoadError(
                            f"Failed to load plugin '{plugin_id}' "
                            f"during activation."
                        )
                    instance = load_result.get("instance")

                if instance is not None:
                    start_method = getattr(instance, "start", None)
                    if callable(start_method):
                        result = start_method()
                        if asyncio.iscoroutine(result):
                            await result

                plugin.state = PluginState.RUNNING
                plugin.started_at = time.monotonic()
                self._active_instances[plugin_id] = instance
                self._registry.update_state(plugin_id, PluginState.RUNNING)

                self._stats["activations"] += 1

                event = PluginEvent(
                    event_type=PluginEventType.STARTED,
                    plugin_id=plugin_id,
                    data={"activation": True},
                )
                await self._event_bus.publish(event)

                logger.info("Activated plugin '%s'.", plugin_id)
                return {
                    "success": True,
                    "plugin_id": plugin_id,
                    "state": PluginState.RUNNING.value,
                }
            except Exception as e:
                self._stats["errors"] += 1
                logger.error(
                    "Failed to activate plugin '%s': %s", plugin_id, e
                )
                raise PluginStartError(
                    f"Failed to activate plugin '{plugin_id}': {e}"
                ) from e

    async def deactivate_plugin(
        self, plugin_id: str
    ) -> Dict[str, Any]:
        """Deactivate a plugin, transitioning it from RUNNING to LOADED.

        Unlike stop, deactivation keeps the plugin loaded for fast
        re-activation.

        Args:
            plugin_id: The plugin identifier to deactivate.

        Returns:
            Result dictionary with ``success`` and state keys.
        """
        plugin = self._registry.get_plugin(plugin_id)
        if plugin is None:
            raise PluginNotFoundError(
                f"Plugin '{plugin_id}' not found in registry."
            )

        if plugin.state != PluginState.RUNNING:
            return {
                "success": True,
                "plugin_id": plugin_id,
                "message": "Plugin is not active.",
            }

        try:
            instance = self._active_instances.get(plugin_id)
            if instance is not None:
                stop_method = getattr(instance, "stop", None)
                if callable(stop_method):
                    result = stop_method()
                    if asyncio.iscoroutine(result):
                        await result

            self._active_instances.pop(plugin_id, None)

            plugin.state = PluginState.LOADED
            plugin.stopped_at = time.monotonic()
            self._registry.update_state(plugin_id, PluginState.LOADED)

            self._stats["deactivations"] += 1

            event = PluginEvent(
                event_type=PluginEventType.STOPPED,
                plugin_id=plugin_id,
                data={"deactivation": True},
            )
            await self._event_bus.publish(event)

            logger.info("Deactivated plugin '%s'.", plugin_id)
            return {
                "success": True,
                "plugin_id": plugin_id,
                "state": PluginState.LOADED.value,
            }
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(
                "Failed to deactivate plugin '%s': %s", plugin_id, e
            )
            raise PluginStopError(
                f"Failed to deactivate plugin '{plugin_id}': {e}"
            ) from e

    def is_active(self, plugin_id: str) -> bool:
        """Check if a plugin is currently active (RUNNING).

        Args:
            plugin_id: The plugin identifier to check.

        Returns:
            True if the plugin is in the active instances map.
        """
        return plugin_id in self._active_instances

    def get_active_plugins(self) -> List[str]:
        """Return the list of active plugin identifiers.

        Returns:
            Sorted list of active plugin IDs.
        """
        return sorted(self._active_instances.keys())

    def get_runtime_stats(self) -> Dict[str, Any]:
        """Get runtime statistics.

        Returns:
            A dictionary with active counts, runtime metrics,
            and sub-component stats.
        """
        return {
            "active_plugins": len(self._active_instances),
            "active_plugin_ids": self.get_active_plugins(),
            "runtime_contexts": len(self._runtime_contexts),
            "stats": dict(self._stats),
            "registry": self._registry.get_stats(),
            "loader": self._loader.get_stats(),
            "sandbox": self._sandbox.get_stats(),
            "event_bus": self._event_bus.get_stats(),
        }

    async def recover_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Attempt automatic recovery of a failed plugin.

        Args:
            plugin_id: The plugin identifier to recover.

        Returns:
            Result dictionary with recovery status.
        """
        plugin = self._registry.get_plugin(plugin_id)
        if plugin is None:
            raise PluginNotFoundError(
                f"Plugin '{plugin_id}' not found in registry."
            )

        if plugin.state != PluginState.FAILED:
            return {
                "success": True,
                "plugin_id": plugin_id,
                "message": "Plugin is not in FAILED state.",
            }

        try:
            self._stats["recoveries"] += 1
            logger.info(
                "Attempting recovery for failed plugin '%s'.", plugin_id
            )
            return await self.start_plugin(plugin_id)
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(
                "Recovery failed for plugin '%s': %s", plugin_id, e
            )
            raise PluginError(
                f"Recovery failed for plugin '{plugin_id}': {e}"
            ) from e

    def _build_runtime_context(self, plugin_id: str) -> RuntimeContext:
        """Build a :class:`RuntimeContext` for a plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            A new RuntimeContext instance.
        """
        return RuntimeContext(
            plugin_id=plugin_id,
            configuration=None,
            eventbus=self._event_bus,
            logger=logging.getLogger(f"plugin.{plugin_id}"),
            metrics=None,
            tracing=None,
            secrets=None,
            crypto=None,
            feature_flags=None,
        )

    @staticmethod
    def _get_sandbox_config(plugin: Plugin) -> Dict[str, Any]:
        """Extract sandbox configuration from a plugin's metadata.

        Args:
            plugin: The plugin data object.

        Returns:
            A dictionary of sandbox configuration options.
        """
        config: Dict[str, Any] = {}
        metadata = plugin.metadata or {}
        sandbox_config = metadata.get("sandbox", {})
        if isinstance(sandbox_config, dict):
            config.update(sandbox_config)
        return config