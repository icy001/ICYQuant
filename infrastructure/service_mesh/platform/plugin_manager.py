"""Mesh Plugin Manager for the Service Mesh Platform.

Provides ``MeshPluginManager`` for plugin lifecycle management
including install, load, unload, upgrade, and hot reload.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from .plugin_sdk import (
    MeshPlugin,
    MeshPluginContext,
    PluginCategory,
)
from .telemetry import PlatformTelemetry
from .metrics import PlatformMetrics

logger = logging.getLogger(__name__)


class PluginState(str, Enum):
    """Lifecycle state of a plugin."""

    DISCOVERED = "discovered"
    LOADED = "loaded"
    RUNNING = "running"
    RELOADING = "reloading"
    STOPPED = "stopped"
    ERROR = "error"


class PluginRecord:
    """Record of a managed plugin."""

    def __init__(
        self,
        plugin_id: str,
        plugin: MeshPlugin,
        category: PluginCategory = PluginCategory.CUSTOM,
    ) -> None:
        self.plugin_id = plugin_id
        self.plugin = plugin
        self.category = category
        self.state = PluginState.DISCOVERED
        self.installed_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.last_reload: Optional[datetime] = None
        self.reload_count = 0
        self.error_count = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.plugin.name,
            "version": self.plugin.version,
            "category": self.category.value,
            "state": self.state.value,
            "installed_at": self.installed_at.isoformat(),
            "started_at": (
                self.started_at.isoformat()
                if self.started_at
                else None
            ),
            "last_reload": (
                self.last_reload.isoformat()
                if self.last_reload
                else None
            ),
            "reload_count": self.reload_count,
            "error_count": self.error_count,
        }


class MeshPluginManager:
    """Manages mesh plugin lifecycle."""

    def __init__(
        self,
        telemetry: Optional[PlatformTelemetry] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._telemetry = telemetry or PlatformTelemetry()
        self._metrics = metrics or PlatformMetrics()
        self._plugins: Dict[str, PluginRecord] = {}
        self._category_index: Dict[str, List[str]] = {}
        self._plugin_contexts: Dict[str, MeshPluginContext] = {}
        self._lifecycle_hooks: Dict[str, List[Callable]] = {}
        self._started = False

    async def start(self) -> Dict[str, Any]:
        self._started = True
        self._telemetry.log_plugin(
            "plugin_manager", "started",
        )
        return {"success": True}

    async def stop(self) -> Dict[str, Any]:
        """Stop all plugins."""
        for plugin_id in list(self._plugins.keys()):
            try:
                await self.unload(plugin_id)
            except Exception as exc:
                logger.warning(
                    "Failed to unload plugin '%s': %s",
                    plugin_id,
                    exc,
                )
        self._started = False
        self._telemetry.log_plugin(
            "plugin_manager", "stopped",
        )
        return {"success": True}

    @property
    def is_running(self) -> bool:
        return self._started

    async def install(
        self,
        plugin_class: Type[MeshPlugin],
        category: PluginCategory = PluginCategory.CUSTOM,
        plugin_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Install a plugin by class."""
        plugin = plugin_class()
        pid = plugin_id or f"plugin-{plugin.name}-{int(time.monotonic())}"

        record = PluginRecord(pid, plugin, category)
        record.state = PluginState.LOADED

        with self._lock:
            self._plugins[pid] = record
            cat_key = category.value
            if cat_key not in self._category_index:
                self._category_index[cat_key] = []
            self._category_index[cat_key].append(pid)

        self._metrics.increment_plugin_total(
            {"action": "install", "category": category.value}
        )
        self._telemetry.log_plugin(
            plugin.name, "installed",
            {"plugin_id": pid, "category": category.value},
        )
        logger.info(
            "Installed plugin '%s' (id=%s, category=%s).",
            plugin.name,
            pid,
            category.value,
        )
        return {"success": True, "plugin_id": pid}

    async def load(
        self, plugin_id: str
    ) -> Dict[str, Any]:
        """Load and initialize a plugin."""
        record = self._plugins.get(plugin_id)
        if record is None:
            return {"success": False, "error": "Plugin not found"}

        if record.state == PluginState.RUNNING:
            return {"success": True, "already_running": True}

        context = self._plugin_contexts.get(
            plugin_id
        ) or MeshPluginContext(
            record.plugin.name,
            telemetry=self._telemetry,
            metrics=self._metrics,
        )

        try:
            result = await record.plugin.initialize(context)
            if result.get("success"):
                record.state = PluginState.RUNNING
                record.started_at = datetime.utcnow()
                self._plugin_contexts[plugin_id] = context
                self._fire_hooks("on_load", record)
                self._telemetry.log_plugin(
                    record.plugin.name, "loaded",
                    {"plugin_id": plugin_id},
                )
                logger.info(
                    "Loaded plugin '%s'.", record.plugin.name
                )
                return {"success": True, "plugin_id": plugin_id}
            else:
                record.state = PluginState.ERROR
                record.error_count += 1
                return result
        except Exception as exc:
            record.state = PluginState.ERROR
            record.error_count += 1
            self._telemetry.log_error(
                "plugin_manager",
                "load_failed",
                str(exc),
                {"plugin_id": plugin_id},
            )
            return {
                "success": False,
                "error": str(exc),
                "plugin_id": plugin_id,
            }

    async def unload(
        self, plugin_id: str
    ) -> Dict[str, Any]:
        """Unload and shutdown a plugin."""
        record = self._plugins.get(plugin_id)
        if record is None:
            return {"success": False, "error": "Plugin not found"}

        context = self._plugin_contexts.get(plugin_id)

        try:
            result = await record.plugin.shutdown(context)
            record.state = PluginState.STOPPED
            self._fire_hooks("on_unload", record)
            self._telemetry.log_plugin(
                record.plugin.name, "unloaded",
                {"plugin_id": plugin_id},
            )
            logger.info(
                "Unloaded plugin '%s'.", record.plugin.name
            )
            return {"success": True, "plugin_id": plugin_id}
        except Exception as exc:
            record.state = PluginState.ERROR
            record.error_count += 1
            return {
                "success": False,
                "error": str(exc),
                "plugin_id": plugin_id,
            }

    async def upgrade(
        self,
        plugin_id: str,
        new_plugin_class: Type[MeshPlugin],
    ) -> Dict[str, Any]:
        """Upgrade a plugin to a new version."""
        record = self._plugins.get(plugin_id)
        if record is None:
            return {"success": False, "error": "Plugin not found"}

        # Unload old plugin
        if record.state == PluginState.RUNNING:
            await self.unload(plugin_id)

        # Replace with new plugin
        new_plugin = new_plugin_class()
        record.plugin = new_plugin
        record.state = PluginState.LOADED
        record.last_reload = datetime.utcnow()
        record.reload_count += 1

        # Load new plugin
        result = await self.load(plugin_id)

        self._metrics.increment_plugin_total(
            {"action": "upgrade", "plugin_id": plugin_id}
        )
        self._telemetry.log_plugin(
            new_plugin.name, "upgraded",
            {"plugin_id": plugin_id},
        )
        logger.info(
            "Upgraded plugin '%s' to v%s.",
            plugin_id,
            new_plugin.version,
        )
        return result

    async def reload(
        self, plugin_id: str
    ) -> Dict[str, Any]:
        """Hot-reload a plugin."""
        record = self._plugins.get(plugin_id)
        if record is None:
            return {"success": False, "error": "Plugin not found"}

        record.state = PluginState.RELOADING
        record.reload_count += 1
        record.last_reload = datetime.utcnow()

        context = self._plugin_contexts.get(plugin_id)

        try:
            result = await record.plugin.shutdown(context)
            if not result.get("success"):
                return result

            result = await record.plugin.initialize(context)
            if result.get("success"):
                record.state = PluginState.RUNNING
                self._telemetry.log_plugin(
                    record.plugin.name, "reloaded",
                    {"plugin_id": plugin_id,
                     "reload_count": record.reload_count},
                )
                logger.info(
                    "Reloaded plugin '%s'.", plugin_id
                )
                return {
                    "success": True,
                    "plugin_id": plugin_id,
                    "reload_count": record.reload_count,
                }
            else:
                record.state = PluginState.ERROR
                return result
        except Exception as exc:
            record.state = PluginState.ERROR
            record.error_count += 1
            return {
                "success": False,
                "error": str(exc),
                "plugin_id": plugin_id,
            }

    async def process_request(
        self,
        request: Dict[str, Any],
        categories: Optional[List[PluginCategory]] = None,
    ) -> Dict[str, Any]:
        """Process a request through all running plugins."""
        results: Dict[str, Any] = {}

        for plugin_id, record in self._plugins.items():
            if record.state != PluginState.RUNNING:
                continue
            if categories and record.category not in categories:
                continue

            context = self._plugin_contexts.get(plugin_id)
            try:
                result = await record.plugin.on_request(
                    request, context
                )
                results[plugin_id] = result
            except Exception as exc:
                record.plugin.on_error(exc, context)
                record.error_count += 1
                results[plugin_id] = {
                    "success": False,
                    "error": str(exc),
                }

        return {"success": True, "plugin_results": results}

    async def process_response(
        self,
        response: Dict[str, Any],
        categories: Optional[List[PluginCategory]] = None,
    ) -> Dict[str, Any]:
        """Process a response through all running plugins."""
        results: Dict[str, Any] = {}

        for plugin_id, record in self._plugins.items():
            if record.state != PluginState.RUNNING:
                continue
            if categories and record.category not in categories:
                continue

            context = self._plugin_contexts.get(plugin_id)
            try:
                result = await record.plugin.on_response(
                    response, context
                )
                results[plugin_id] = result
            except Exception as exc:
                record.plugin.on_error(exc, context)
                record.error_count += 1
                results[plugin_id] = {
                    "success": False,
                    "error": str(exc),
                }

        return {"success": True, "plugin_results": results}

    def register_lifecycle_hook(
        self,
        event: str,
        hook: Callable,
    ) -> None:
        if event not in self._lifecycle_hooks:
            self._lifecycle_hooks[event] = []
        self._lifecycle_hooks[event].append(hook)

    def _fire_hooks(
        self, event: str, record: PluginRecord
    ) -> None:
        hooks = self._lifecycle_hooks.get(event, [])
        for hook in hooks:
            try:
                hook(record.to_dict())
            except Exception as exc:
                logger.warning(
                    "Lifecycle hook failed for '%s': %s",
                    event,
                    exc,
                )

    def get_plugin(self, plugin_id: str) -> Optional[PluginRecord]:
        return self._plugins.get(plugin_id)

    def list_plugins(
        self, category: Optional[PluginCategory] = None
    ) -> List[Dict[str, Any]]:
        plugins = list(self._plugins.values())
        if category:
            plugins = [p for p in plugins if p.category == category]
        return [p.to_dict() for p in plugins]

    def get_plugins_by_category(
        self, category: PluginCategory
    ) -> List[PluginRecord]:
        ids = self._category_index.get(category.value, [])
        return [
            self._plugins[pid]
            for pid in ids
            if pid in self._plugins
        ]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_plugins": len(self._plugins),
                "running_plugins": sum(
                    1
                    for p in self._plugins.values()
                    if p.state == PluginState.RUNNING
                ),
                "by_state": self._count_by_state(),
                "by_category": self._count_by_category(),
                "lifecycle_hooks": {
                    k: len(v)
                    for k, v in self._lifecycle_hooks.items()
                },
            }

    def _count_by_state(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for p in self._plugins.values():
            state = p.state.value
            counts[state] = counts.get(state, 0) + 1
        return counts

    def _count_by_category(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for p in self._plugins.values():
            cat = p.category.value
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"MeshPluginManager(plugins={len(self._plugins)}, "
                f"running={self._started})"
            )
