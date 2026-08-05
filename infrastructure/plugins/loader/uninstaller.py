"""Plugin uninstaller for the loader subsystem.

Performs full plugin uninstallation by executing a controlled
lifecycle sequence: stop → unload → unregister → cleanup. Each
step is isolated so that failures in one stage do not prevent
subsequent cleanup stages from running.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from ..exceptions import PluginNotFoundError, PluginUnloadError
from ..registry import PluginRegistry
from .importer import PluginImporter

logger = logging.getLogger(__name__)


class PluginUninstaller:
    """Uninstalls plugins via a structured lifecycle sequence.

    The uninstaller coordinates plugin stop, module unload, registry
    removal, and file cleanup. Each step returns a result dict
    with a ``success`` flag and an ``errors`` list, allowing the
    caller to inspect which stages succeeded and which failed.

    Attributes:
        registry: The plugin registry to remove plugins from.
        importer: The module importer used to unload cached modules.
    """

    def __init__(
        self,
        registry: Optional[PluginRegistry] = None,
        importer: Optional[PluginImporter] = None,
    ) -> None:
        self._registry = registry
        self._importer = importer or PluginImporter()
        self._uninstall_count: int = 0
        self._failure_count: int = 0

    async def uninstall(self, plugin_id: str) -> Dict[str, Any]:
        """Perform a full uninstallation of a plugin.

        Executes the lifecycle sequence:
        1. :meth:`stop_plugin`   – gracefully stop the plugin.
        2. :meth:`unload_module` – remove the loaded module.
        3. :meth:`unregister_plugin` – remove from the registry.
        4. :meth:`cleanup_files` – delete plugin files.

        Args:
            plugin_id: The identifier of the plugin to uninstall.

        Returns:
            A result dictionary with:

            - ``success`` (bool): Overall success status.
            - ``plugin_id`` (str): The plugin that was uninstalled.
            - ``steps`` (dict): Per-step result dictionaries.
            - ``errors`` (list): Combined error messages.
        """
        if not plugin_id:
            return {
                "success": False,
                "plugin_id": "",
                "steps": {},
                "errors": ["Plugin id cannot be empty"],
            }

        steps: Dict[str, Dict[str, Any]] = {}
        all_errors: list = []

        stop_result = await self.stop_plugin(plugin_id)
        steps["stop"] = stop_result
        if not stop_result.get("success"):
            all_errors.extend(stop_result.get("errors", []))

        unload_result = await self.unload_module(plugin_id)
        steps["unload"] = unload_result
        if not unload_result.get("success"):
            all_errors.extend(unload_result.get("errors", []))

        unregister_result = await self.unregister_plugin(plugin_id)
        steps["unregister"] = unregister_result
        if not unregister_result.get("success"):
            all_errors.extend(unregister_result.get("errors", []))

        plugin_dir = self._resolve_plugin_dir(plugin_id)
        if plugin_dir:
            cleanup_result = await self.cleanup_files(plugin_dir)
            steps["cleanup"] = cleanup_result
            if not cleanup_result.get("success"):
                all_errors.extend(cleanup_result.get("errors", []))

        success = len(all_errors) == 0
        if success:
            self._uninstall_count += 1
            logger.info("Uninstalled plugin '%s'.", plugin_id)
        else:
            self._failure_count += 1
            logger.warning(
                "Uninstall of '%s' completed with errors: %s",
                plugin_id,
                all_errors,
            )

        return {
            "success": success,
            "plugin_id": plugin_id,
            "steps": steps,
            "errors": all_errors,
        }

    async def stop_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Gracefully stop a running plugin.

        Calls the plugin's ``on_stop`` and ``on_unload`` hooks (if
        they exist and are callable). Errors during hooks are
        logged but do not prevent subsequent cleanup.

        Args:
            plugin_id: The plugin identifier to stop.

        Returns:
            Result dict with ``success``, ``plugin_id``, and
            ``errors`` keys.
        """
        if not plugin_id:
            return self._result("", False, ["Plugin id cannot be empty"])

        plugin = self._get_plugin(plugin_id)
        if plugin is None:
            logger.debug(
                "Plugin '%s' not found for stopping; treating as stopped.",
                plugin_id,
            )
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
                "on_stop failed for '%s': %s", plugin_id, exc
            )
            return self._result(
                plugin_id, False, [f"on_stop failed: {exc}"]
            )

        try:
            on_unload = getattr(instance, "on_unload", None)
            if callable(on_unload):
                result = on_unload()
                if hasattr(result, "__await__"):
                    await result
        except Exception as exc:
            logger.warning(
                "on_unload failed for '%s': %s", plugin_id, exc
            )

        return self._result(plugin_id, True, [])

    async def unload_module(self, plugin_id: str) -> Dict[str, Any]:
        """Unload a plugin module from the importer cache.

        Determines the module path from the plugin's entrypoint
        and delegates to :class:`PluginImporter.unload_module`.

        Args:
            plugin_id: The plugin identifier whose module to unload.

        Returns:
            Result dict with ``success``, ``plugin_id``, and
            ``errors`` keys.
        """
        if not plugin_id:
            return self._result("", False, ["Plugin id cannot be empty"])

        plugin = self._get_plugin(plugin_id)
        if plugin is not None:
            entrypoint = getattr(plugin, "entrypoint", "") or ""
            module_path = (
                entrypoint.split(":")[0] if ":" in entrypoint else entrypoint
            )
            if module_path:
                try:
                    self._importer.unload_module(module_path)
                    logger.debug(
                        "Unloaded module '%s' for plugin '%s'.",
                        module_path,
                        plugin_id,
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to unload module '%s': %s",
                        module_path,
                        exc,
                    )
                    return self._result(
                        plugin_id,
                        False,
                        [f"Failed to unload module: {exc}"],
                    )

        return self._result(plugin_id, True, [])

    async def unregister_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Remove a plugin from the registry.

        Args:
            plugin_id: The plugin identifier to unregister.

        Returns:
            Result dict with ``success``, ``plugin_id``, and
            ``errors`` keys.
        """
        if not plugin_id:
            return self._result("", False, ["Plugin id cannot be empty"])

        if self._registry is not None:
            try:
                self._registry.unregister(plugin_id)
                logger.debug(
                    "Unregistered plugin '%s'.", plugin_id
                )
            except Exception as exc:
                return self._result(
                    plugin_id,
                    False,
                    [f"Failed to unregister plugin: {exc}"],
                )

        return self._result(plugin_id, True, [])

    async def cleanup_files(self, plugin_dir: str) -> Dict[str, Any]:
        """Remove plugin files from disk.

        Recursively deletes the plugin directory if it exists.

        Args:
            plugin_dir: Path to the plugin directory to remove.

        Returns:
            Result dict with ``success``, ``plugin_id``, and
            ``errors`` keys.
        """
        if not plugin_dir:
            return self._result("", True, [])

        path = Path(plugin_dir)
        if not path.exists():
            return self._result(str(path), True, [])

        try:
            shutil.rmtree(str(path), ignore_errors=True)
            logger.info(
                "Cleaned up plugin files at '%s'.", plugin_dir
            )
            return self._result(str(path), True, [])
        except OSError as exc:
            logger.error(
                "Failed to cleanup files at '%s': %s",
                plugin_dir,
                exc,
            )
            return self._result(
                str(path),
                False,
                [f"Failed to cleanup files: {exc}"],
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the uninstaller state to a dictionary.

        Returns:
            A dictionary with uninstallation counts and status.
        """
        total = self._uninstall_count + self._failure_count
        return {
            "uninstall_count": self._uninstall_count,
            "failure_count": self._failure_count,
            "total_attempts": total,
            "success_rate": (
                self._uninstall_count / total if total > 0 else 0.0
            ),
            "has_registry": self._registry is not None,
        }

    def _get_plugin(self, plugin_id: str) -> Optional[Any]:
        """Retrieve a plugin from the registry."""
        if self._registry is not None:
            return self._registry.get_plugin(plugin_id)
        return None

    def _resolve_plugin_dir(self, plugin_id: str) -> Optional[str]:
        """Resolve the plugin directory path from registry metadata."""
        plugin = self._get_plugin(plugin_id)
        if plugin is None:
            return None
        metadata = getattr(plugin, "metadata", {}) or {}
        return metadata.get("path")

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