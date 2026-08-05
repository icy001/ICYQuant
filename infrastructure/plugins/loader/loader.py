"""Main plugin loader for the ICYQuant plugin framework.

The :class:`PluginLoader` is the unified async entry point for all
plugin loading operations. It integrates the directory scanner,
module importer, dependency resolver, and cache to provide a
complete plugin lifecycle management API.

Architecture::

        PluginLoader
             │
    ┌────────┼────────┐
    │        │        │
  Scanner  Importer  Resolver
    │        │        │
    └────────┼────────┘
             │
       Cache / Metrics
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..exceptions import (
    PluginLoadError,
    PluginNotFoundError,
    PluginUnloadError,
)
from ..manifest import PluginManifest
from ..models import Plugin, PluginState
from ..registry import PluginRegistry
from .cache import LoaderCache
from .importer import PluginImporter
from .resolver import DependencyResolver2
from .scanner import DirectoryScanner

logger = logging.getLogger(__name__)


class PluginLoader:
    """Unified async plugin loader.

    Orchestrates plugin discovery, installation, loading,
    unloading, reloading, and lifecycle management. Integrates
    specialized sub-components for each responsibility.

    Thread safety is provided via an :class:`asyncio.Lock` that
    guards load/unload operations, and a
    :class:`~threading.RLock` in the cache for synchronous
    access.
    """

    def __init__(
        self,
        scanner: Optional[DirectoryScanner] = None,
        importer: Optional[PluginImporter] = None,
        resolver: Optional[DependencyResolver2] = None,
        cache: Optional[LoaderCache] = None,
        registry: Optional[PluginRegistry] = None,
    ) -> None:
        self._scanner = scanner or DirectoryScanner()
        self._importer = importer or PluginImporter()
        self._resolver = resolver or DependencyResolver2()
        self._cache = cache or LoaderCache()
        self._registry = registry or PluginRegistry()

        self._plugins: Dict[str, Plugin] = {}
        self._instances: Dict[str, Any] = {}
        self._load_lock = asyncio.Lock()

        self._metrics: Dict[str, int] = {
            "discoveries": 0,
            "loads": 0,
            "reloads": 0,
            "unloads": 0,
            "installs": 0,
            "uninstalls": 0,
            "starts": 0,
            "stops": 0,
            "errors": 0,
        }

    async def discover(
        self, plugin_dirs: Optional[List[str]] = None
    ) -> List[PluginManifest]:
        """Discover plugins by scanning directories for manifests.

        Args:
            plugin_dirs: Directories to scan. When ``None`` or empty,
                returns cached manifests from previous discoveries.

        Returns:
            List of discovered :class:`PluginManifest` objects.
        """
        if not plugin_dirs:
            return []

        all_manifests: List[PluginManifest] = []
        for plugin_dir in plugin_dirs:
            try:
                manifests = self._scanner.scan(plugin_dir)
                for manifest in manifests:
                    self._cache.set_manifest(manifest.id, manifest)
                all_manifests.extend(manifests)
            except Exception as exc:
                self._metrics["errors"] += 1
                logger.exception(
                    "Error scanning plugin directory '%s': %s",
                    plugin_dir,
                    exc,
                )

        self._metrics["discoveries"] += len(all_manifests)

        duplicates = self._scanner.detect_duplicates(all_manifests)
        if duplicates:
            for dup_id in duplicates:
                logger.warning(
                    "Duplicate plugin id during discover: %s", dup_id
                )

        compatible = self._scanner.check_compatibility(all_manifests)
        logger.info(
            "Discovered %d plugins (%d compatible).",
            len(all_manifests),
            len(compatible),
        )
        return compatible

    async def install(
        self,
        manifest: PluginManifest,
        plugin_dir: Optional[str] = None,
    ) -> Plugin:
        """Install a plugin from a manifest.

        Creates a :class:`Plugin` record and registers it with
        the plugin registry. If ``plugin_dir`` is provided, the
        manifest is copied into that directory.

        Args:
            manifest: The plugin manifest to install.
            plugin_dir: Optional target directory for the plugin.

        Returns:
            The newly created :class:`Plugin` object.

        Raises:
            PluginLoadError: If the manifest is invalid or the
                plugin cannot be installed.
        """
        if manifest is None:
            raise PluginLoadError("Manifest cannot be None")

        manifest_errors = manifest.validate()
        if manifest_errors:
            raise PluginLoadError(
                f"Manifest validation failed: {'; '.join(manifest_errors)}"
            )

        if plugin_dir is not None:
            target = self._resolve_plugin_dir(plugin_dir, manifest)
            self._ensure_plugin_directory(target, manifest)

        plugin = self._create_plugin_from_manifest(manifest)
        self._registry.register(plugin.id, plugin)
        self._plugins[plugin.id] = plugin

        self._cache.set_manifest(plugin.id, manifest)
        self._metrics["installs"] += 1

        logger.info("Installed plugin '%s'.", plugin.id)
        return plugin

    async def load(
        self,
        plugin_id: str,
        context: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Load a plugin by its identifier.

        Resolves the manifest (from cache or by discovering it),
        imports the plugin module, instantiates the plugin, and
        registers it. If the plugin has unmet dependencies, the
        load is deferred until dependencies are satisfied.

        Args:
            plugin_id: The plugin identifier to load.
            context: Optional context passed to the plugin constructor.

        Returns:
            Result dictionary with keys:

            - ``success``: ``True`` if the plugin loaded successfully.
            - ``plugin_id``: The loaded plugin id.
            - ``instance``: The plugin instance (or ``None``).
            - ``message``: Human-readable result description.

        Raises:
            PluginNotFoundError: If the plugin manifest cannot be found.
            PluginLoadError: If loading fails.
        """
        if not plugin_id:
            raise PluginLoadError("Plugin id cannot be empty")

        async with self._load_lock:
            manifest = self._cache.get_manifest(plugin_id)
            if manifest is None:
                raise PluginNotFoundError(
                    f"No manifest found for plugin '{plugin_id}'"
                )

            existing = self._instances.get(plugin_id)
            if existing is not None:
                return {
                    "success": True,
                    "plugin_id": plugin_id,
                    "instance": existing,
                    "message": "Plugin already loaded.",
                }

            try:
                entrypoint = manifest.entrypoint or plugin_id
                instance = self._importer.load_plugin(
                    entrypoint, context=context
                )

                if instance is None:
                    raise PluginLoadError(
                        f"Failed to instantiate plugin '{plugin_id}'"
                    )

                plugin = self._plugins.get(plugin_id)
                if plugin is None:
                    plugin = self._create_plugin_from_manifest(manifest)
                    self._registry.register(plugin_id, plugin)
                    self._plugins[plugin_id] = plugin

                plugin.instance = instance
                plugin.state = PluginState.LOADED
                plugin.loaded_at = datetime.now()
                self._registry.update_state(plugin_id, PluginState.LOADED)

                self._instances[plugin_id] = instance
                self._cache.set_module(
                    entrypoint,
                    self._importer.import_module(
                        entrypoint.split(":")[0]
                        if ":" in entrypoint
                        else entrypoint
                    ),
                )

                self._metrics["loads"] += 1

                logger.info("Loaded plugin '%s'.", plugin_id)
                return {
                    "success": True,
                    "plugin_id": plugin_id,
                    "instance": instance,
                    "message": "Plugin loaded successfully.",
                }
            except (PluginLoadError, PluginNotFoundError):
                self._metrics["errors"] += 1
                raise
            except Exception as exc:
                self._metrics["errors"] += 1
                logger.exception(
                    "Unexpected error loading plugin '%s': %s",
                    plugin_id,
                    exc,
                )
                raise PluginLoadError(
                    f"Failed to load plugin '{plugin_id}': {exc}"
                ) from exc

    async def unload(self, plugin_id: str) -> Dict[str, Any]:
        """Unload a plugin, removing its instance and cached module.

        Args:
            plugin_id: The plugin identifier to unload.

        Returns:
            Result dictionary with ``success``, ``plugin_id``,
            and ``message`` keys.

        Raises:
            PluginNotFoundError: If the plugin is not currently loaded.
        """
        if not plugin_id:
            raise PluginUnloadError("Plugin id cannot be empty")

        async with self._load_lock:
            if plugin_id not in self._instances:
                raise PluginNotFoundError(
                    f"Plugin '{plugin_id}' is not loaded"
                )

            instance = self._instances.pop(plugin_id, None)

            if instance is not None:
                on_unload = getattr(instance, "on_unload", None)
                if callable(on_unload):
                    try:
                        result = on_unload()
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as exc:
                        logger.warning(
                            "on_unload failed for '%s': %s",
                            plugin_id,
                            exc,
                        )

            plugin = self._plugins.get(plugin_id)
            if plugin is not None:
                plugin.state = PluginState.STOPPED
                plugin.stopped_at = datetime.now()
                plugin.instance = None
                self._registry.update_state(
                    plugin_id, PluginState.STOPPED
                )

            self._cache.invalidate_plugin(plugin_id)
            self._importer.unload_module(plugin_id)

            self._metrics["unloads"] += 1

            logger.info("Unloaded plugin '%s'.", plugin_id)
            return {
                "success": True,
                "plugin_id": plugin_id,
                "message": "Plugin unloaded successfully.",
            }

    async def reload(
        self,
        plugin_id: str,
        context: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Hot-reload a plugin by unloading and re-loading it.

        Saves the plugin's state before unloading and restores it
        after re-loading.

        Args:
            plugin_id: The plugin identifier to reload.
            context: Optional context passed to the new instance.

        Returns:
            Result dictionary with ``success``, ``plugin_id``,
            ``instance``, and ``duration_seconds`` keys.
        """
        start = time.monotonic()

        async with self._load_lock:
            manifest = self._cache.get_manifest(plugin_id)
            if manifest is None:
                raise PluginNotFoundError(
                    f"No manifest found for plugin '{plugin_id}'"
                )

            state: Dict[str, Any] = {}
            existing = self._instances.get(plugin_id)
            if existing is not None:
                state = self._save_state(existing)

            if plugin_id in self._instances:
                try:
                    await self.unload(plugin_id)
                except PluginNotFoundError:
                    pass

            instance = await self.load(plugin_id, context=context)

            if instance.get("success") and state:
                new_instance = instance.get("instance")
                if new_instance is not None:
                    self._restore_state(new_instance, state)

            elapsed = time.monotonic() - start
            self._metrics["reloads"] += 1

            logger.info(
                "Reloaded plugin '%s' in %.4fs.", plugin_id, elapsed
            )
            return {
                "success": True,
                "plugin_id": plugin_id,
                "instance": instance.get("instance"),
                "duration_seconds": elapsed,
            }

    async def uninstall(self, plugin_id: str) -> Dict[str, Any]:
        """Uninstall a plugin completely.

        Unloads the plugin, removes it from the registry, and
        clears all associated caches.

        Args:
            plugin_id: The plugin identifier to uninstall.

        Returns:
            Result dictionary with ``success``, ``plugin_id``,
            and ``message`` keys.
        """
        if not plugin_id:
            raise PluginUnloadError("Plugin id cannot be empty")

        async with self._load_lock:
            was_loaded = plugin_id in self._instances
            if was_loaded:
                try:
                    await self.unload(plugin_id)
                except PluginNotFoundError:
                    pass

            self._registry.unregister(plugin_id)
            self._plugins.pop(plugin_id, None)
            self._instances.pop(plugin_id, None)
            self._cache.invalidate_plugin(plugin_id)

            self._metrics["uninstalls"] += 1

            logger.info("Uninstalled plugin '%s'.", plugin_id)
            return {
                "success": True,
                "plugin_id": plugin_id,
                "message": "Plugin uninstalled successfully.",
            }

    async def start_all(self) -> Dict[str, Any]:
        """Start all loaded plugins.

        Iterates through all registered plugins and transitions
        them to the ``RUNNING`` state by calling their ``start``
        or ``run`` method if available.

        Returns:
            Result dictionary with ``started``, ``failed``, and
            ``total`` keys.
        """
        started: List[str] = []
        failed: List[Dict[str, str]] = []

        for plugin_id, instance in list(self._instances.items()):
            try:
                start_method = getattr(instance, "start", None)
                if start_method is not None and callable(start_method):
                    result = start_method()
                    if asyncio.iscoroutine(result):
                        await result

                plugin = self._plugins.get(plugin_id)
                if plugin is not None:
                    plugin.state = PluginState.RUNNING
                    plugin.started_at = datetime.now()
                    self._registry.update_state(
                        plugin_id, PluginState.RUNNING
                    )

                started.append(plugin_id)
                self._metrics["starts"] += 1
            except Exception as exc:
                self._metrics["errors"] += 1
                failed.append(
                    {"plugin_id": plugin_id, "error": str(exc)}
                )
                logger.exception(
                    "Failed to start plugin '%s': %s", plugin_id, exc
                )

        return {
            "started": started,
            "failed": failed,
            "total": len(self._instances),
        }

    async def stop_all(self) -> Dict[str, Any]:
        """Stop all running plugins.

        Iterates through all loaded plugins and transitions them
        to the ``STOPPED`` state by calling their ``stop`` method
        if available.

        Returns:
            Result dictionary with ``stopped``, ``failed``, and
            ``total`` keys.
        """
        stopped: List[str] = []
        failed: List[Dict[str, str]] = []

        for plugin_id, instance in list(self._instances.items()):
            try:
                stop_method = getattr(instance, "stop", None)
                if stop_method is not None and callable(stop_method):
                    result = stop_method()
                    if asyncio.iscoroutine(result):
                        await result

                plugin = self._plugins.get(plugin_id)
                if plugin is not None:
                    plugin.state = PluginState.STOPPED
                    plugin.stopped_at = datetime.now()
                    self._registry.update_state(
                        plugin_id, PluginState.STOPPED
                    )

                stopped.append(plugin_id)
                self._metrics["stops"] += 1
            except Exception as exc:
                self._metrics["errors"] += 1
                failed.append(
                    {"plugin_id": plugin_id, "error": str(exc)}
                )
                logger.exception(
                    "Failed to stop plugin '%s': %s", plugin_id, exc
                )

        return {
            "stopped": stopped,
            "failed": failed,
            "total": len(self._instances),
        }

    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """Get a plugin's data object by its identifier.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            The :class:`Plugin` data object, or ``None`` if not found.
        """
        return self._plugins.get(plugin_id)

    def list_plugins(self) -> List[Plugin]:
        """Return a list of all registered plugins.

        Returns:
            List of :class:`Plugin` data objects.
        """
        return list(self._plugins.values())

    def get_stats(self) -> Dict[str, Any]:
        """Return loader statistics and sub-component stats.

        Returns:
            Dictionary with loader metrics and sub-component stats.
        """
        return {
            "plugins_registered": len(self._plugins),
            "plugins_loaded": len(self._instances),
            "metrics": dict(self._metrics),
            "scanner": self._scanner.to_dict(),
            "importer": self._importer.get_stats(),
            "resolver": self._resolver.to_dict(),
            "cache": self._cache.get_stats(),
            "registry": self._registry.get_stats(),
        }

    def validate_entrypoint(self, entrypoint: str) -> bool:
        """Validate a plugin entrypoint format.

        Args:
            entrypoint: Entrypoint string (e.g. 'module:Class' or 'module').

        Returns:
            True if the entrypoint has a valid format.
        """
        if not entrypoint or not isinstance(entrypoint, str):
            return False
        if ":" in entrypoint:
            module_path, _, class_name = entrypoint.partition(":")
            if not module_path or not class_name:
                return False
            if not module_path.replace(".", "").replace("_", "").isalnum():
                return False
            if not class_name.replace("_", "").isalnum():
                return False
            return True
        return bool(entrypoint.replace(".", "").replace("_", "").isalnum())

    def load_module(self, module_path: str) -> Any:
        """Load a module by path.

        Args:
            module_path: Dotted module path.

        Returns:
            Module object or None on failure.
        """
        try:
            return self._importer.import_module(module_path)
        except Exception:
            return None

    def load_plugin(self, entrypoint: str, context: Any = None) -> Any:
        """Load a plugin from entrypoint (synchronous).

        Args:
            entrypoint: Plugin entrypoint string.
            context: Optional context for the plugin.

        Returns:
            Plugin instance or None on failure.
        """
        try:
            return self._importer.load_plugin(entrypoint, context)
        except Exception:
            return None

    async def shutdown(self) -> None:
        """Gracefully shut down the loader.

        Stops all running plugins, clears caches, and unregisters
        all plugins.
        """
        logger.info("Shutting down plugin loader.")

        try:
            await self.stop_all()
        except Exception:
            logger.exception("Error during stop_all at shutdown.")

        self._cache.clear()
        self._importer.invalidate_all()

        self._registry.clear()
        self._plugins.clear()
        self._instances.clear()

        for key in self._metrics:
            self._metrics[key] = 0

        logger.info("Plugin loader shut down complete.")

    def _create_plugin_from_manifest(
        self, manifest: PluginManifest
    ) -> Plugin:
        """Create a :class:`Plugin` data object from a manifest.

        Args:
            manifest: The plugin manifest.

        Returns:
            A new :class:`Plugin` instance.
        """
        return Plugin(
            id=manifest.id,
            name=manifest.name,
            version=manifest.version,
            author=manifest.author,
            description=manifest.description,
            entrypoint=manifest.entrypoint,
            api_version=manifest.api,
            state=PluginState.REGISTERED,
            capabilities=list(manifest.capabilities),
            permissions=list(manifest.permissions),
            dependencies=list(manifest.dependencies),
            config=dict(manifest.config),
            metadata=dict(manifest.metadata),
            installed_at=datetime.now(),
        )

    @staticmethod
    def _resolve_plugin_dir(
        base_dir: str, manifest: PluginManifest
    ) -> str:
        """Resolve the target directory for a plugin installation.

        Args:
            base_dir: Base directory for plugin installations.
            manifest: The plugin manifest.

        Returns:
            Absolute path for the plugin's directory.
        """
        import os

        return os.path.join(base_dir, manifest.id)

    @staticmethod
    def _ensure_plugin_directory(
        plugin_dir: str, manifest: PluginManifest
    ) -> None:
        """Create the plugin directory and write the manifest file.

        Args:
            plugin_dir: Target directory path.
            manifest: The manifest to write.
        """
        import os

        os.makedirs(plugin_dir, exist_ok=True)
        manifest_path = os.path.join(plugin_dir, "manifest.yaml")
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(manifest.to_yaml())

    @staticmethod
    def _save_state(instance: Any) -> Dict[str, Any]:
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
    def _restore_state(instance: Any, state: Dict[str, Any]) -> None:
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