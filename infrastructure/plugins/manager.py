from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .models import Plugin, PluginPriority, PluginState
from .manifest import PluginManifest
from .metadata import MetadataRegistry
from .registry import PluginRegistry
from .loader import PluginLoader
from .lifecycle import PluginLifecycle
from .dependency import DependencyResolver
from .capabilities import Capability, CapabilityRegistry
from .permissions import Permission, PermissionChecker, PermissionSet
from .configuration import ConfigurationManager
from .hooks import HookPoint, HookRegistry
from .events import PluginEvent, PluginEventBus, PluginEventType
from .metrics import PluginMetrics
from .health import PluginHealth
from .diagnostics import DiagnosticInfo, PluginDiagnostics
from .context import ContextBuilder, PluginContext
from .validator import PluginValidator
from .exceptions import (
    PluginAlreadyExistsError,
    PluginCircularDependencyError,
    PluginDependencyError,
    PluginError,
    PluginInstallError,
    PluginLoadError,
    PluginMissingDependencyError,
    PluginNotFoundError,
    PluginPermissionError,
    PluginStartError,
    PluginStateError,
    PluginStopError,
    PluginValidationError,
)

logger = logging.getLogger(__name__)


class PluginManager:
    """Central orchestrator for the plugin framework.

    Unified entry point for:
    - Install, Load, Enable, Disable, Reload, Remove
    - Dependency resolution and ordering
    - Lifecycle management
    - Capability and permission enforcement
    - Health checks and diagnostics

    Architecture::

        Plugin Manager
              │
    ┌─────────┼─────────┐
    │         │         │
  Registry  Loader  Lifecycle
    │         │         │
    └─────────┼─────────┘
              │
       Plugin Instance
              │
    Capability / Permission / Context
    """

    def __init__(self) -> None:
        self._registry = PluginRegistry()
        self._loader = PluginLoader()
        self._lifecycle = PluginLifecycle()
        self._resolver = DependencyResolver()
        self._capability_registry = CapabilityRegistry()
        self._permission_checker = PermissionChecker()
        self._config_manager = ConfigurationManager()
        self._hooks = HookRegistry()
        self._event_bus = PluginEventBus()
        self._metrics = PluginMetrics()
        self._health = PluginHealth(
            registry=self._registry, loader=self._loader
        )
        self._diagnostics = PluginDiagnostics()
        self._validator = PluginValidator()
        self._metadata_registry = MetadataRegistry()

        self._enabled: set[str] = set()
        self._initialized = False
        self._shutdown_started = False

    # ── Install / Uninstall ──────────────────────────────────────

    async def install(
        self, manifest: PluginManifest, context: PluginContext | None = None
    ) -> Plugin:
        """Install a plugin from a manifest.

        Validates the manifest, checks for duplicates, registers the
        plugin, and fires ``before_install`` / ``after_install`` hooks.
        """
        if manifest is None:
            raise PluginInstallError("Manifest cannot be None.")

        errors = self._validator.validate_manifest(manifest)
        if errors:
            raise PluginValidationError(
                f"Manifest validation failed for '{manifest.id}': {'; '.join(errors)}"
            )

        await self._hooks.execute(HookPoint.BEFORE_INSTALL, manifest.id, manifest)

        if self._registry.has(manifest.id):
            raise PluginAlreadyExistsError(
                f"Plugin '{manifest.id}' is already installed."
            )

        plugin = Plugin(
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
            installed_at=datetime.utcnow(),
        )

        self._registry.register(plugin.id, plugin)

        self._config_manager.register(plugin.id, dict(manifest.config))

        self._capability_registry.register(
            plugin.id,
            [Capability(c) for c in manifest.capabilities],
        )

        self._permission_checker.declare(
            plugin.id,
            PermissionSet.from_list(manifest.permissions),
        )

        from .metadata import PluginMetadata

        meta = PluginMetadata(
            plugin_id=plugin.id,
            name=plugin.name,
            version=plugin.version,
            author=plugin.author,
            description=plugin.description,
        )
        self._metadata_registry.register(meta)

        self._enabled.add(plugin.id)

        self._diagnostics.record_state_change(
            plugin.id, "", PluginState.REGISTERED.value
        )

        event = PluginEvent(
            event_type=PluginEventType.INSTALLED,
            plugin_id=plugin.id,
            data=plugin.to_dict(),
        )
        await self._event_bus.publish(event)

        await self._hooks.execute(HookPoint.AFTER_INSTALL, plugin.id, plugin)

        logger.info("Installed plugin '%s' v%s.", plugin.id, plugin.version)
        return plugin

    async def install_from_dict(
        self, data: Dict[str, Any], context: PluginContext | None = None
    ) -> Plugin:
        """Install a plugin from a dictionary (manifest data)."""
        manifest = PluginManifest.from_dict(data)
        return await self.install(manifest, context=context)

    async def uninstall(self, plugin_id: str) -> Dict[str, Any]:
        """Uninstall a plugin: stop, unload, and remove all traces."""
        plugin = self._registry.get_plugin(plugin_id)
        if plugin is None:
            raise PluginNotFoundError(f"Plugin '{plugin_id}' not found.")

        state = plugin.state
        if state == PluginState.RUNNING:
            await self.stop(plugin_id)

        if state in (PluginState.LOADED, PluginState.INITIALIZED, PluginState.FAILED, PluginState.STOPPED):
            await self.unload(plugin_id)

        self._capability_registry.unregister(plugin_id)
        self._permission_checker.revoke_all(plugin_id)
        self._config_manager.unregister(plugin_id)
        self._metadata_registry.unregister(plugin_id)
        self._enabled.discard(plugin_id)

        self._registry.unregister(plugin_id)

        self._diagnostics.record_state_change(
            plugin_id, state.value, PluginState.UNINSTALLED.value
        )

        event = PluginEvent(
            event_type=PluginEventType.REMOVED,
            plugin_id=plugin_id,
            data={"state": state.value},
        )
        await self._event_bus.publish(event)

        logger.info("Uninstalled plugin '%s'.", plugin_id)
        return {
            "plugin_id": plugin_id,
            "previous_state": state.value,
            "success": True,
        }

    # ── Load / Unload ────────────────────────────────────────────

    async def load(
        self, plugin_id: str, context: PluginContext | None = None
    ) -> Dict[str, Any]:
        """Load a plugin and its dependencies (transitively).

        Dependencies are resolved, topologically sorted, and loaded
        before the target plugin.
        """
        plugin = self._registry.get_plugin(plugin_id)
        if plugin is None:
            raise PluginNotFoundError(f"Plugin '{plugin_id}' not found.")

        if plugin.state == PluginState.RUNNING:
            return {"success": True, "plugin_id": plugin_id, "message": "Plugin is already running."}

        if not self.is_enabled(plugin_id):
            raise PluginStateError(f"Plugin '{plugin_id}' is disabled. Enable it first.")

        resolution = await self._resolve_dependencies(plugin_id)
        if not resolution.get("valid", False):
            cycles = resolution.get("cycles", [])
            missing = resolution.get("missing", {})
            if cycles:
                raise PluginCircularDependencyError(
                    f"Circular dependency detected for '{plugin_id}': {cycles}"
                )
            if missing:
                raise PluginMissingDependencyError(
                    f"Missing dependencies for '{plugin_id}': {missing}"
                )
            raise PluginDependencyError(
                f"Dependency resolution failed for '{plugin_id}'."
            )

        load_order = resolution.get("order", [])

        for dep_id in load_order:
            dep_plugin = self._registry.get_plugin(dep_id)
            if dep_plugin is None:
                continue
            if dep_plugin.state in (PluginState.RUNNING, PluginState.INITIALIZED, PluginState.LOADED):
                continue
            if not self.is_enabled(dep_id):
                logger.debug("Skipping disabled dependency '%s'.", dep_id)
                continue

            dep_ctx = context
            if dep_ctx is None:
                dep_ctx = await self._create_context(dep_plugin)

            await self._hooks.execute(HookPoint.BEFORE_LOAD, dep_id, dep_plugin)

            load_start = time.monotonic()
            try:
                entrypoint = dep_plugin.entrypoint or dep_plugin.id
                if entrypoint:
                    instance = await self._loader.load_plugin(entrypoint, context=dep_ctx)
                    dep_plugin.instance = instance
            except Exception as e:
                dep_plugin.state = PluginState.FAILED
                dep_plugin.error = str(e)
                self._registry.update_state(dep_id, PluginState.FAILED)
                self._metrics.record_fail(dep_id, str(e))
                self._diagnostics.record_error(dep_id, str(e))
                raise PluginLoadError(
                    f"Failed to load dependency '{dep_id}': {e}"
                ) from e

            load_duration = time.monotonic() - load_start
            self._metrics.record_load(dep_id, load_duration)

            result = await self._lifecycle.transition_to(
                dep_id, PluginState.LOADED, dep_plugin
            )
            if not result.get("success"):
                dep_plugin.state = PluginState.FAILED
                dep_plugin.error = result.get("error", "Failed to transition to LOADED")
                self._registry.update_state(dep_id, PluginState.FAILED)
                self._metrics.record_fail(dep_id, dep_plugin.error)
                raise PluginLoadError(
                    f"Failed to load dependency '{dep_id}': {dep_plugin.error}"
                )

            self._registry.update_state(dep_id, PluginState.LOADED)
            dep_plugin.loaded_at = datetime.utcnow()
            self._diagnostics.record_state_change(
                dep_id, PluginState.REGISTERED.value, PluginState.LOADED.value
            )

            await self._hooks.execute(HookPoint.AFTER_LOAD, dep_id, dep_plugin)

        ctx = context
        if ctx is None:
            ctx = await self._create_context(plugin)

        await self._hooks.execute(HookPoint.BEFORE_LOAD, plugin_id, plugin)

        load_start = time.monotonic()
        try:
            entrypoint = plugin.entrypoint or plugin.id
            if entrypoint:
                instance = await self._loader.load_plugin(entrypoint, context=ctx)
                plugin.instance = instance
        except Exception as e:
            plugin.state = PluginState.FAILED
            plugin.error = str(e)
            self._registry.update_state(plugin_id, PluginState.FAILED)
            self._metrics.record_fail(plugin_id, str(e))
            self._diagnostics.record_error(plugin_id, str(e))
            raise PluginLoadError(
                f"Failed to load plugin '{plugin_id}': {e}"
            ) from e

        load_duration = time.monotonic() - load_start
        self._metrics.record_load(plugin_id, load_duration)

        result = await self._lifecycle.transition_to(
            plugin_id, PluginState.LOADED, plugin
        )
        if not result.get("success"):
            plugin.state = PluginState.FAILED
            plugin.error = result.get("error", "Failed to transition to LOADED")
            self._registry.update_state(plugin_id, PluginState.FAILED)
            self._metrics.record_fail(plugin_id, plugin.error)
            raise PluginLoadError(
                f"Failed to load plugin '{plugin_id}': {plugin.error}"
            )

        self._registry.update_state(plugin_id, PluginState.LOADED)
        plugin.loaded_at = datetime.utcnow()
        self._diagnostics.record_state_change(
            plugin_id, PluginState.REGISTERED.value, PluginState.LOADED.value
        )

        event = PluginEvent(
            event_type=PluginEventType.LOADED,
            plugin_id=plugin_id,
            data=plugin.to_dict(),
        )
        await self._event_bus.publish(event)

        await self._hooks.execute(HookPoint.AFTER_LOAD, plugin_id, plugin)

        logger.info("Loaded plugin '%s'.", plugin_id)
        return {
            "plugin_id": plugin_id,
            "state": plugin.state.value,
            "success": True,
        }

    async def unload(self, plugin_id: str) -> Dict[str, Any]:
        """Unload a plugin: stop it first if running, then transition to UNINSTALLED."""
        plugin = self._registry.get_plugin(plugin_id)
        if plugin is None:
            raise PluginNotFoundError(f"Plugin '{plugin_id}' not found.")

        if plugin.state == PluginState.RUNNING:
            await self.stop(plugin_id)

        await self._hooks.execute(HookPoint.BEFORE_UNLOAD, plugin_id, plugin)

        result = await self._lifecycle.shutdown(plugin_id, plugin)

        if plugin.instance is not None:
            unload_method = getattr(plugin.instance, "on_unload", None)
            if callable(unload_method):
                try:
                    unload_method()
                except Exception as e:
                    logger.error("Plugin '%s' on_unload failed: %s", plugin_id, e)

        plugin.instance = None
        self._registry.update_state(plugin_id, PluginState.UNINSTALLED)
        self._metrics.record_unload(plugin_id)

        self._diagnostics.record_state_change(
            plugin_id, plugin.state.value if plugin.state else "", PluginState.UNINSTALLED.value
        )

        event = PluginEvent(
            event_type=PluginEventType.UNLOADED,
            plugin_id=plugin_id,
            data=plugin.to_dict(),
        )
        await self._event_bus.publish(event)

        await self._hooks.execute(HookPoint.AFTER_UNLOAD, plugin_id, plugin)

        logger.info("Unloaded plugin '%s'.", plugin_id)
        return {
            "plugin_id": plugin_id,
            "success": True,
        }

    # ── Start / Stop ──────────────────────────────────────────────

    async def start(self, plugin_id: str) -> Dict[str, Any]:
        """Start a plugin: load it if needed, then initialize and start."""
        plugin = self._registry.get_plugin(plugin_id)
        if plugin is None:
            raise PluginNotFoundError(f"Plugin '{plugin_id}' not found.")

        if not self.is_enabled(plugin_id):
            raise PluginStateError(f"Plugin '{plugin_id}' is disabled. Enable it first.")

        if plugin.state == PluginState.RUNNING:
            return {"success": True, "plugin_id": plugin_id, "message": "Plugin is already running."}

        if plugin.state in (PluginState.REGISTERED, PluginState.FAILED, PluginState.STOPPED):
            await self.load(plugin_id)

        await self._hooks.execute(HookPoint.BEFORE_START, plugin_id, plugin)

        start_time = time.monotonic()

        init_result = await self._lifecycle.initialize(plugin_id, plugin)
        if not init_result.get("success"):
            plugin.state = PluginState.FAILED
            plugin.error = init_result.get("error", "Initialization failed")
            self._registry.update_state(plugin_id, PluginState.FAILED)
            self._metrics.record_fail(plugin_id, plugin.error)
            self._diagnostics.record_error(plugin_id, plugin.error)
            raise PluginStartError(
                f"Failed to start plugin '{plugin_id}': {plugin.error}"
            )

        start_result = await self._lifecycle.start(plugin_id, plugin)
        if not start_result.get("success"):
            plugin.state = PluginState.FAILED
            plugin.error = start_result.get("error", "Start failed")
            self._registry.update_state(plugin_id, PluginState.FAILED)
            self._metrics.record_fail(plugin_id, plugin.error)
            self._diagnostics.record_error(plugin_id, plugin.error)
            raise PluginStartError(
                f"Failed to start plugin '{plugin_id}': {plugin.error}"
            )

        self._registry.update_state(plugin_id, PluginState.RUNNING)
        plugin.state = PluginState.RUNNING
        plugin.started_at = datetime.utcnow()
        self._metrics.record_state_change(
            plugin_id, PluginState.INITIALIZED.value, PluginState.RUNNING.value
        )

        start_duration = time.monotonic() - start_time
        self._metrics.record_evaluation(plugin_id, start_duration, success=True)

        self._diagnostics.record_state_change(
            plugin_id, "", PluginState.RUNNING.value
        )

        event = PluginEvent(
            event_type=PluginEventType.STARTED,
            plugin_id=plugin_id,
            data=plugin.to_dict(),
        )
        await self._event_bus.publish(event)

        await self._hooks.execute(HookPoint.AFTER_START, plugin_id, plugin)

        logger.info("Started plugin '%s'.", plugin_id)
        return {
            "plugin_id": plugin_id,
            "state": plugin.state.value,
            "success": True,
        }

    async def stop(self, plugin_id: str) -> Dict[str, Any]:
        """Stop a running plugin."""
        plugin = self._registry.get_plugin(plugin_id)
        if plugin is None:
            raise PluginNotFoundError(f"Plugin '{plugin_id}' not found.")

        if plugin.state != PluginState.RUNNING:
            return {"success": True, "plugin_id": plugin_id, "message": "Plugin is not running."}

        await self._hooks.execute(HookPoint.BEFORE_STOP, plugin_id, plugin)

        result = await self._lifecycle.stop(plugin_id, plugin)
        if not result.get("success"):
            raise PluginStopError(
                f"Failed to stop plugin '{plugin_id}': {result.get('error')}"
            )

        self._registry.update_state(plugin_id, PluginState.STOPPED)
        plugin.state = PluginState.STOPPED
        plugin.stopped_at = datetime.utcnow()
        self._metrics.record_state_change(
            plugin_id, PluginState.RUNNING.value, PluginState.STOPPED.value
        )

        self._diagnostics.record_state_change(
            plugin_id, PluginState.RUNNING.value, PluginState.STOPPED.value
        )

        event = PluginEvent(
            event_type=PluginEventType.STOPPED,
            plugin_id=plugin_id,
            data=plugin.to_dict(),
        )
        await self._event_bus.publish(event)

        await self._hooks.execute(HookPoint.AFTER_STOP, plugin_id, plugin)

        logger.info("Stopped plugin '%s'.", plugin_id)
        return {
            "plugin_id": plugin_id,
            "state": plugin.state.value,
            "success": True,
        }

    async def start_all(self) -> Dict[str, Any]:
        """Start all enabled plugins in dependency order."""
        all_plugins = self._registry.get_all()
        if not all_plugins:
            return {"started": [], "failed": [], "skipped": []}

        graph: Dict[str, List[str]] = {}
        for p in all_plugins:
            graph[p.id] = list(p.dependencies)

        available = {p.id for p in all_plugins}
        resolution = self._resolver.resolve(graph, available)
        load_order = resolution.get("order", [])

        started: List[str] = []
        failed: List[Dict[str, str]] = []
        skipped: List[str] = []

        for plugin_id in load_order:
            if not self.is_enabled(plugin_id):
                skipped.append(plugin_id)
                continue
            try:
                await self.start(plugin_id)
                started.append(plugin_id)
            except Exception as e:
                failed.append({"plugin_id": plugin_id, "error": str(e)})
                logger.error("Failed to start '%s': %s", plugin_id, e)

        return {
            "started": started,
            "failed": failed,
            "skipped": skipped,
            "total": len(load_order),
        }

    async def stop_all(self) -> Dict[str, Any]:
        """Stop all running plugins in reverse dependency order."""
        running = self._registry.get_by_state(PluginState.RUNNING.value)
        if not running:
            return {"stopped": [], "failed": [], "message": "No running plugins."}

        running_ids = {p.id for p in running}
        graph: Dict[str, List[str]] = {}
        for p in self._registry.get_all():
            graph[p.id] = [d for d in p.dependencies if d in running_ids]

        resolution = self._resolver.resolve(graph, running_ids)
        stop_order = list(reversed(resolution.get("order", list(running_ids))))

        stopped: List[str] = []
        failed: List[Dict[str, str]] = []

        for plugin_id in stop_order:
            try:
                await self.stop(plugin_id)
                stopped.append(plugin_id)
            except Exception as e:
                failed.append({"plugin_id": plugin_id, "error": str(e)})
                logger.error("Failed to stop '%s': %s", plugin_id, e)

        return {
            "stopped": stopped,
            "failed": failed,
        }

    # ── Enable / Disable ──────────────────────────────────────────

    async def enable(self, plugin_id: str) -> Dict[str, Any]:
        """Enable a plugin (allow it to be loaded/started)."""
        plugin = self._registry.get_plugin(plugin_id)
        if plugin is None:
            raise PluginNotFoundError(f"Plugin '{plugin_id}' not found.")

        self._enabled.add(plugin_id)

        self._diagnostics.record(
            DiagnosticInfo(
                plugin_id=plugin_id,
                category="state",
                message="Plugin enabled.",
                details={"action": "enable"},
            )
        )

        event = PluginEvent(
            event_type=PluginEventType.CONFIG_CHANGED,
            plugin_id=plugin_id,
            data={"enabled": True},
        )
        await self._event_bus.publish(event)

        logger.info("Enabled plugin '%s'.", plugin_id)
        return {"plugin_id": plugin_id, "enabled": True, "success": True}

    async def disable(self, plugin_id: str) -> Dict[str, Any]:
        """Disable a plugin: stop it if running, then mark as disabled."""
        plugin = self._registry.get_plugin(plugin_id)
        if plugin is None:
            raise PluginNotFoundError(f"Plugin '{plugin_id}' not found.")

        if plugin.state == PluginState.RUNNING:
            await self.stop(plugin_id)

        self._enabled.discard(plugin_id)

        self._diagnostics.record(
            DiagnosticInfo(
                plugin_id=plugin_id,
                category="state",
                message="Plugin disabled.",
                details={"action": "disable"},
            )
        )

        event = PluginEvent(
            event_type=PluginEventType.CONFIG_CHANGED,
            plugin_id=plugin_id,
            data={"enabled": False},
        )
        await self._event_bus.publish(event)

        logger.info("Disabled plugin '%s'.", plugin_id)
        return {"plugin_id": plugin_id, "enabled": False, "success": True}

    def is_enabled(self, plugin_id: str) -> bool:
        """Check if a plugin is enabled."""
        return plugin_id in self._enabled

    # ── Reload ────────────────────────────────────────────────────

    async def reload(
        self, plugin_id: str, new_manifest: PluginManifest | None = None
    ) -> Dict[str, Any]:
        """Reload a plugin: stop, unload, optionally update manifest, then load and start."""
        plugin = self._registry.get_plugin(plugin_id)
        if plugin is None:
            raise PluginNotFoundError(f"Plugin '{plugin_id}' not found.")

        was_running = plugin.state == PluginState.RUNNING

        reload_start = time.monotonic()

        if was_running:
            await self.stop(plugin_id)

        if plugin.state != PluginState.UNINSTALLED:
            await self.unload(plugin_id)

        if new_manifest is not None:
            errors = self._validator.validate_manifest(new_manifest)
            if errors:
                raise PluginValidationError(
                    f"New manifest validation failed: {'; '.join(errors)}"
                )

            self.unregister_plugin_data(plugin_id)

            plugin = Plugin(
                id=new_manifest.id,
                name=new_manifest.name,
                version=new_manifest.version,
                author=new_manifest.author,
                description=new_manifest.description,
                entrypoint=new_manifest.entrypoint,
                api_version=new_manifest.api,
                state=PluginState.REGISTERED,
                capabilities=list(new_manifest.capabilities),
                permissions=list(new_manifest.permissions),
                dependencies=list(new_manifest.dependencies),
                config=dict(new_manifest.config),
                metadata=dict(new_manifest.metadata),
                installed_at=datetime.utcnow(),
            )
            self._registry.register(plugin.id, plugin)

            self._config_manager.register(plugin.id, dict(new_manifest.config))
            self._capability_registry.register(
                plugin.id,
                [Capability(c) for c in new_manifest.capabilities],
            )
            self._permission_checker.declare(
                plugin.id,
                PermissionSet.from_list(new_manifest.permissions),
            )
            self._enabled.add(plugin.id)

        await self.load(plugin_id)

        if was_running:
            await self.start(plugin_id)

        reload_duration = time.monotonic() - reload_start
        self._metrics.record_reload(plugin_id, reload_duration)

        event = PluginEvent(
            event_type=PluginEventType.RELOADED,
            plugin_id=plugin_id,
            data=plugin.to_dict(),
        )
        await self._event_bus.publish(event)

        logger.info("Reloaded plugin '%s'.", plugin_id)
        return {
            "plugin_id": plugin_id,
            "success": True,
            "duration_seconds": reload_duration,
        }

    async def reload_all(self) -> Dict[str, Any]:
        """Reload all running plugins."""
        running = self._registry.get_by_state(PluginState.RUNNING.value)
        results: List[Dict[str, Any]] = []
        failed: List[Dict[str, str]] = []

        for plugin in running:
            try:
                result = await self.reload(plugin.id)
                results.append(result)
            except Exception as e:
                failed.append({"plugin_id": plugin.id, "error": str(e)})

        return {
            "reloaded": results,
            "failed": failed,
            "total": len(running),
        }

    # ── Query ─────────────────────────────────────────────────────

    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """Get a plugin by ID."""
        return self._registry.get_plugin(plugin_id)

    def list_plugins(self, state: PluginState | None = None) -> List[Plugin]:
        """List plugins, optionally filtered by state."""
        if state is None:
            return self._registry.get_all()
        return self._registry.get_by_state(state.value)

    def find_by_capability(self, capability: Capability) -> List[Plugin]:
        """Find plugins that provide a specific capability."""
        plugin_ids = self._capability_registry.get_plugins_with_capability(capability)
        results: List[Plugin] = []
        for pid in plugin_ids:
            plugin = self._registry.get_plugin(pid)
            if plugin is not None:
                results.append(plugin)
        return results

    def find_by_permission(self, permission: Permission) -> List[Plugin]:
        """Find plugins that have a specific permission."""
        all_plugins = self._registry.get_all()
        return [
            p for p in all_plugins
            if self._permission_checker.check(p.id, permission)
        ]

    # ── Lifecycle ─────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Bootstrap the plugin manager."""
        if self._initialized:
            return
        self._initialized = True
        logger.info("Plugin manager initialized.")

    async def shutdown(self) -> None:
        """Graceful shutdown: stop all running plugins and clean up."""
        if self._shutdown_started:
            return
        self._shutdown_started = True

        logger.info("Plugin manager shutting down...")

        await self.stop_all()

        plugins = self._registry.get_all()
        for plugin in plugins:
            if plugin.instance is not None:
                unload_method = getattr(plugin.instance, "on_unload", None)
                if callable(unload_method):
                    try:
                        unload_method()
                    except Exception as e:
                        logger.error("Error during unload of '%s': %s", plugin.id, e)
                plugin.instance = None

        await self._event_bus.shutdown()
        self._registry.clear()
        self._initialized = False

        logger.info("Plugin manager shut down.")

    # ── Observability ──────────────────────────────────────────────

    async def health_check(self) -> Dict[str, Any]:
        """Run a full health check."""
        return await self._health.check()

    def get_diagnostics(self, plugin_id: str = "") -> List[Dict[str, Any]]:
        """Get diagnostics for a plugin or all plugins."""
        return self._diagnostics.get_diagnostics(plugin_id=plugin_id)

    def get_metrics_snapshot(self) -> Dict[str, Any]:
        """Get a snapshot of all metrics."""
        return self._metrics.snapshot()

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics from all sub-systems."""
        return {
            "registry": self._registry.get_stats(),
            "loader": self._loader.get_stats(),
            "lifecycle": self._lifecycle.get_stats(),
            "capabilities": self._capability_registry.to_dict(),
            "permissions": self._permission_checker.to_dict(),
            "configurations": self._config_manager.list_configs(),
            "events": self._event_bus.get_stats(),
            "metrics": self._metrics.get_stats(),
            "health": self._health.get_stats(),
            "diagnostics": self._diagnostics.get_stats(),
            "enabled_plugins": sorted(self._enabled),
            "validator": self._validator.get_stats(),
        }

    # ── Internal ──────────────────────────────────────────────────

    async def _resolve_dependencies(self, plugin_id: str) -> Dict[str, Any]:
        """Resolve dependencies for a plugin, returning topological order."""
        plugin = self._registry.get_plugin(plugin_id)
        if plugin is None:
            return {"order": [], "cycles": [], "missing": {}, "valid": False}

        visited: set[str] = set()
        graph: Dict[str, List[str]] = {}

        def collect(pid: str) -> None:
            if pid in visited:
                return
            visited.add(pid)
            p = self._registry.get_plugin(pid)
            if p is None:
                graph[pid] = []
                return
            graph[pid] = list(p.dependencies)
            for dep in p.dependencies:
                collect(dep)

        collect(plugin_id)

        available = set(self._registry.list_ids())
        return self._resolver.resolve(graph, available)

    async def _create_context(self, plugin: Plugin) -> PluginContext:
        """Create a PluginContext for a plugin using the ContextBuilder."""
        config = self._config_manager.get_config(plugin.id)
        config_dict = config.all() if config is not None else dict(plugin.config)

        builder = ContextBuilder(plugin.id)
        builder.with_config(config_dict)
        builder.with_eventbus(self._event_bus)
        builder.with_metrics(self._metrics)

        metadata = self._metadata_registry.get(plugin.id)
        if metadata is not None:
            builder.with_secrets(metadata)

        return builder.build()

    def unregister_plugin_data(self, plugin_id: str) -> None:
        """Clean up all data for a plugin without removing it from registry."""
        self._capability_registry.unregister(plugin_id)
        self._permission_checker.revoke_all(plugin_id)
        self._config_manager.unregister(plugin_id)
        self._metadata_registry.unregister(plugin_id)
        self._enabled.discard(plugin_id)

    def get_config_manager(self) -> ConfigurationManager:
        """Return the configuration manager."""
        return self._config_manager

    def get_event_bus(self) -> PluginEventBus:
        """Return the event bus."""
        return self._event_bus

    def get_capability_registry(self) -> CapabilityRegistry:
        """Return the capability registry."""
        return self._capability_registry

    def get_permission_checker(self) -> PermissionChecker:
        """Return the permission checker."""
        return self._permission_checker

    def get_dependency_resolver(self) -> DependencyResolver:
        """Return the dependency resolver."""
        return self._resolver

    def get_validator(self) -> PluginValidator:
        """Return the plugin validator."""
        return self._validator

    def get_lifecycle(self) -> PluginLifecycle:
        """Return the plugin lifecycle manager."""
        return self._lifecycle

    def get_registry(self) -> PluginRegistry:
        """Return the plugin registry."""
        return self._registry

    def get_loader(self) -> PluginLoader:
        """Return the plugin loader."""
        return self._loader

    def get_hooks(self) -> HookRegistry:
        """Return the hook registry."""
        return self._hooks

    def get_diagnostics_module(self) -> PluginDiagnostics:
        """Return the diagnostics module."""
        return self._diagnostics

    def get_health_module(self) -> PluginHealth:
        """Return the health module."""
        return self._health

    def get_metadata_registry(self) -> MetadataRegistry:
        """Return the metadata registry."""
        return self._metadata_registry

    def get_metrics_module(self) -> PluginMetrics:
        """Return the metrics module."""
        return self._metrics