"""Plugin reloader for the loader subsystem.

Implements hot-reload of plugins by stopping, unloading, re-importing,
and re-initializing them. Plugin state is preserved across reloads
when the plugin exposes ``get_state``/``set_state`` or
``__getstate__``/``__setstate__`` methods.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from ..exceptions import PluginNotFoundError, PluginReloadError
from ..manifest import PluginManifest
from ..models import Plugin, PluginState
from ..registry import PluginRegistry
from .importer import PluginImporter

logger = logging.getLogger(__name__)


class PluginReloader:
    """Hot-reloads plugins by re-importing and re-instantiating.

    The reloader coordinates with :class:`PluginImporter` to
    invalidate cached modules and import fresh ones. It preserves
    plugin state across reloads when the plugin instance supports
    state save/restore.

    Attributes:
        registry: The plugin registry to update plugin state in.
        importer: The module importer used for reloading modules.
    """

    def __init__(
        self,
        registry: Optional[PluginRegistry] = None,
        importer: Optional[PluginImporter] = None,
    ) -> None:
        self._registry = registry
        self._importer = importer or PluginImporter()
        self._reload_count: int = 0
        self._failure_count: int = 0

    async def reload(
        self,
        plugin_id: str,
        new_manifest: Optional[PluginManifest] = None,
    ) -> Dict[str, Any]:
        """Reload a plugin with an optional updated manifest.

        Full reload sequence:
        1. Save current plugin state.
        2. :meth:`stop_plugin` – gracefully stop the plugin.
        3. :meth:`unload_module` – remove the old module.
        4. :meth:`reload_module` – import the fresh module.
        5. :meth:`initialize_plugin` – create a new instance.
        6. :meth:`resume_service` – restore saved state.

        Args:
            plugin_id: The plugin identifier to reload.
            new_manifest: Optional updated manifest. When provided,
                the plugin's manifest is replaced before reloading.

        Returns:
            Result dict with ``success``, ``plugin_id``,
            ``instance``, ``duration_seconds``, and ``errors`` keys.
        """
        if not plugin_id:
            return {
                "success": False,
                "plugin_id": "",
                "instance": None,
                "errors": ["Plugin id cannot be empty"],
            }

        start = time.monotonic()
        saved_state: Dict[str, Any] = {}
        errors: list = []

        try:
            plugin = self._get_plugin(plugin_id)
            if plugin is None:
                return {
                    "success": False,
                    "plugin_id": plugin_id,
                    "instance": None,
                    "errors": [f"Plugin '{plugin_id}' not found"],
                }

            instance = getattr(plugin, "instance", None)
            if instance is not None:
                saved_state = self._save_plugin_state(instance)

            stop_result = await self.stop_plugin(plugin_id)
            if not stop_result.get("success"):
                errors.extend(stop_result.get("errors", []))
                return self._reload_fail(
                    plugin_id, errors, start
                )

            unload_result = await self.unload_module(plugin_id)
            if not unload_result.get("success"):
                errors.extend(unload_result.get("errors", []))
                return self._reload_fail(
                    plugin_id, errors, start
                )

            if new_manifest is not None:
                self._update_manifest(plugin, new_manifest)

            reload_result = await self.reload_module(plugin_id)
            if not reload_result.get("success"):
                errors.extend(reload_result.get("errors", []))
                return self._reload_fail(
                    plugin_id, errors, start
                )

            init_result = await self.initialize_plugin(plugin_id)
            if not init_result.get("success"):
                errors.extend(init_result.get("errors", []))
                return self._reload_fail(
                    plugin_id, errors, start
                )

            if saved_state:
                await self.resume_service(plugin_id, saved_state)

            elapsed = time.monotonic() - start
            self._reload_count += 1
            logger.info(
                "Reloaded plugin '%s' in %.4fs.", plugin_id, elapsed
            )

            return {
                "success": True,
                "plugin_id": plugin_id,
                "instance": reload_result.get("instance"),
                "duration_seconds": elapsed,
                "errors": [],
            }

        except PluginNotFoundError as exc:
            elapsed = time.monotonic() - start
            return {
                "success": False,
                "plugin_id": plugin_id,
                "instance": None,
                "errors": [str(exc)],
                "duration_seconds": elapsed,
            }
        except Exception as exc:
            elapsed = time.monotonic() - start
            self._failure_count += 1
            logger.exception(
                "Failed to reload plugin '%s': %s", plugin_id, exc
            )
            return {
                "success": False,
                "plugin_id": plugin_id,
                "instance": None,
                "errors": [f"Reload failed: {exc}"],
                "duration_seconds": elapsed,
            }

    async def stop_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Gracefully stop a running plugin before reload.

        Calls the plugin's ``on_stop`` and ``on_unload`` hooks if
        available.

        Args:
            plugin_id: The plugin identifier to stop.

        Returns:
            Result dict with ``success`` and ``errors`` keys.
        """
        if not plugin_id:
            return self._result("", False, ["Plugin id cannot be empty"])

        plugin = self._get_plugin(plugin_id)
        if plugin is None:
            return self._result(plugin_id, True, [])

        instance = getattr(plugin, "instance", None)
        if instance is None:
            return self._result(plugin_id, True, [])

        try:
            on_stop = getattr(instance, "on_stop", None)
            if callable(on_stop):
                result = on_stop()
                if hasattr(result, "__await__"):
                    await result
        except Exception as exc:
            logger.warning(
                "on_stop failed during reload of '%s': %s", plugin_id, exc
            )

        try:
            on_unload = getattr(instance, "on_unload", None)
            if callable(on_unload):
                result = on_unload()
                if hasattr(result, "__await__"):
                    await result
        except Exception as exc:
            logger.warning(
                "on_unload failed during reload of '%s': %s", plugin_id, exc
            )

        plugin.state = PluginState.STOPPED
        plugin.instance = None
        return self._result(plugin_id, True, [])

    async def unload_module(self, plugin_id: str) -> Dict[str, Any]:
        """Remove the old plugin module from the importer cache.

        Args:
            plugin_id: The plugin identifier whose module to unload.

        Returns:
            Result dict with ``success`` and ``errors`` keys.
        """
        if not plugin_id:
            return self._result("", False, ["Plugin id cannot be empty"])

        plugin = self._get_plugin(plugin_id)
        if plugin is None:
            return self._result(plugin_id, True, [])

        entrypoint = getattr(plugin, "entrypoint", "") or ""
        module_path = (
            entrypoint.split(":")[0] if ":" in entrypoint else entrypoint
        )
        if module_path:
            try:
                self._importer.unload_module(module_path)
                logger.debug(
                    "Unloaded module '%s' for reload of '%s'.",
                    module_path,
                    plugin_id,
                )
            except Exception as exc:
                return self._result(
                    plugin_id,
                    False,
                    [f"Failed to unload module: {exc}"],
                )

        return self._result(plugin_id, True, [])

    async def reload_module(self, plugin_id: str) -> Dict[str, Any]:
        """Import a fresh plugin module and instantiate it.

        Uses :class:`PluginImporter.load_plugin` to import the
        module and discover/instantiate the plugin class.

        Args:
            plugin_id: The plugin identifier to reload.

        Returns:
            Result dict with ``success``, ``instance``, and
            ``errors`` keys.
        """
        if not plugin_id:
            return self._result("", False, ["Plugin id cannot be empty"])

        plugin = self._get_plugin(plugin_id)
        if plugin is None:
            return self._result(
                plugin_id,
                False,
                [f"Plugin '{plugin_id}' not found for module reload"],
            )

        entrypoint = getattr(plugin, "entrypoint", "") or ""
        if not entrypoint:
            return self._result(
                plugin_id,
                False,
                ["No entrypoint available for module reload"],
            )

        try:
            self._importer.reload_module(
                entrypoint.split(":")[0]
                if ":" in entrypoint
                else entrypoint
            )
        except Exception as exc:
            return self._result(
                plugin_id,
                False,
                [f"Failed to reload module: {exc}"],
            )

        try:
            context = getattr(plugin, "config", None) or None
            instance = self._importer.load_plugin(entrypoint, context=context)

            if instance is None:
                return self._result(
                    plugin_id,
                    False,
                    ["Plugin class not found or instantiation failed"],
                )

            return {
                "success": True,
                "plugin_id": plugin_id,
                "instance": instance,
                "errors": [],
            }
        except Exception as exc:
            return self._result(
                plugin_id,
                False,
                [f"Failed to load plugin: {exc}"],
            )

    async def initialize_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Initialize a newly reloaded plugin instance.

        Calls the plugin's ``on_init`` hook if available and
        transitions the plugin state to ``INITIALIZED``.

        Args:
            plugin_id: The plugin identifier to initialize.

        Returns:
            Result dict with ``success`` and ``errors`` keys.
        """
        if not plugin_id:
            return self._result("", False, ["Plugin id cannot be empty"])

        plugin = self._get_plugin(plugin_id)
        if plugin is None:
            return self._result(
                plugin_id,
                False,
                [f"Plugin '{plugin_id}' not found for initialization"],
            )

        instance = getattr(plugin, "instance", None)
        if instance is None:
            return self._result(
                plugin_id,
                False,
                ["No plugin instance available for initialization"],
            )

        try:
            on_init = getattr(instance, "on_init", None)
            if callable(on_init):
                result = on_init()
                if hasattr(result, "__await__"):
                    await result
        except Exception as exc:
            return self._result(
                plugin_id,
                False,
                [f"on_init failed: {exc}"],
            )

        plugin.state = PluginState.INITIALIZED
        if self._registry is not None:
            self._registry.update_state(plugin_id, PluginState.INITIALIZED)

        return self._result(plugin_id, True, [])

    async def resume_service(
        self, plugin_id: str, state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Restore plugin state after reload.

        Best-effort state restoration: tries ``set_state``, then
        ``__setstate__``, then falls back to direct attribute
        assignment.

        Args:
            plugin_id: The plugin identifier to resume.
            state: Previously saved state dictionary.

        Returns:
            Result dict with ``success`` and ``errors`` keys.
        """
        if not plugin_id:
            return self._result("", False, ["Plugin id cannot be empty"])

        plugin = self._get_plugin(plugin_id)
        if plugin is None:
            return self._result(
                plugin_id,
                False,
                [f"Plugin '{plugin_id}' not found for state resume"],
            )

        instance = getattr(plugin, "instance", None)
        if instance is None:
            return self._result(
                plugin_id,
                False,
                ["No plugin instance available for state resume"],
            )

        if state:
            self._restore_plugin_state(instance, state)

        try:
            on_start = getattr(instance, "on_start", None)
            if callable(on_start):
                result = on_start()
                if hasattr(result, "__await__"):
                    await result
        except Exception as exc:
            logger.warning(
                "on_start failed during resume of '%s': %s", plugin_id, exc
            )

        plugin.state = PluginState.RUNNING
        if self._registry is not None:
            self._registry.update_state(plugin_id, PluginState.RUNNING)

        return self._result(plugin_id, True, [])

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the reloader state to a dictionary.

        Returns:
            A dictionary with reload counts and status.
        """
        total = self._reload_count + self._failure_count
        return {
            "reload_count": self._reload_count,
            "failure_count": self._failure_count,
            "total_attempts": total,
            "success_rate": (
                self._reload_count / total if total > 0 else 0.0
            ),
            "has_registry": self._registry is not None,
        }

    def _get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """Retrieve a plugin from the registry."""
        if self._registry is not None:
            return self._registry.get_plugin(plugin_id)
        return None

    def _update_manifest(
        self, plugin: Plugin, manifest: PluginManifest
    ) -> None:
        """Update a plugin's manifest data."""
        plugin.name = manifest.name
        plugin.version = manifest.version
        plugin.author = manifest.author
        plugin.description = manifest.description
        plugin.entrypoint = manifest.entrypoint
        plugin.api_version = manifest.api
        plugin.capabilities = list(manifest.capabilities)
        plugin.permissions = list(manifest.permissions)
        plugin.dependencies = list(manifest.dependencies)
        plugin.config = dict(manifest.config)
        plugin.metadata = dict(manifest.metadata)
        logger.debug("Updated manifest for plugin '%s'.", plugin.id)

    @staticmethod
    def _save_plugin_state(instance: Any) -> Dict[str, Any]:
        """Best-effort save of a plugin instance's state."""
        if instance is None:
            return {}

        get_state = getattr(instance, "get_state", None)
        if callable(get_state):
            try:
                result = get_state()
                if isinstance(result, dict):
                    return dict(result)
            except Exception:
                pass

        getstate = getattr(instance, "__getstate__", None)
        if callable(getstate):
            try:
                result = getstate()
                if isinstance(result, dict):
                    return dict(result)
            except Exception:
                pass

        state: Dict[str, Any] = {}
        for attr in dir(instance):
            if attr.startswith("_"):
                continue
            try:
                value = getattr(instance, attr)
                if callable(value):
                    continue
                state[attr] = value
            except Exception:
                continue
        return state

    @staticmethod
    def _restore_plugin_state(instance: Any, state: Dict[str, Any]) -> None:
        """Best-effort restore of a plugin instance's state."""
        if instance is None or not state:
            return

        set_state = getattr(instance, "set_state", None)
        if callable(set_state):
            try:
                set_state(state)
                return
            except Exception:
                pass

        setstate = getattr(instance, "__setstate__", None)
        if callable(setstate):
            try:
                setstate(state)
                return
            except Exception:
                pass

        for key, value in state.items():
            if key.startswith("_"):
                continue
            try:
                setattr(instance, key, value)
            except Exception:
                continue

    def _reload_fail(
        self, plugin_id: str, errors: list, start: float
    ) -> Dict[str, Any]:
        """Build a failure result dict for reload."""
        self._failure_count += 1
        elapsed = time.monotonic() - start
        return {
            "success": False,
            "plugin_id": plugin_id,
            "instance": None,
            "errors": errors,
            "duration_seconds": elapsed,
        }

    @staticmethod
    def _result(
        plugin_id: str, success: bool, errors: list
    ) -> Dict[str, Any]:
        """Build a standardized result dictionary."""
        return {
            "success": success,
            "plugin_id": plugin_id,
            "errors": list(errors),
        }