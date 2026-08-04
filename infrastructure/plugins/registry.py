"""Plugin registry.

Central registry for all plugins in the ICYQuant plugin framework.
Manages plugin registration, lookup, state tracking, and version
management.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Central registry for all plugins.

    Manages plugin registration, lookup, state tracking,
    and version management.
    """

    def __init__(self) -> None:
        self._plugins: Dict[str, Any] = {}
        self._state_index: Dict[str, List[str]] = defaultdict(list)
        self._capability_index: Dict[str, List[str]] = defaultdict(list)
        self._permission_index: Dict[str, List[str]] = defaultdict(list)

    def register(self, plugin_id: str, plugin: Any) -> None:
        if plugin_id in self._plugins:
            logger.warning("Plugin '%s' already registered; replacing.", plugin_id)
            self._unindex(plugin_id)
        self._plugins[plugin_id] = plugin
        self._index(plugin_id, plugin)
        logger.info("Registered plugin '%s'.", plugin_id)

    def unregister(self, plugin_id: str) -> None:
        if plugin_id not in self._plugins:
            logger.warning("Plugin '%s' not found for unregistration.", plugin_id)
            return
        self._unindex(plugin_id)
        del self._plugins[plugin_id]
        logger.info("Unregistered plugin '%s'.", plugin_id)

    def get_plugin(self, plugin_id: str) -> Optional[Any]:
        return self._plugins.get(plugin_id)

    def get_all(self) -> List[Any]:
        return list(self._plugins.values())

    def get_by_state(self, state: str) -> List[Any]:
        ids = self._state_index.get(state, [])
        return [self._plugins[pid] for pid in ids if pid in self._plugins]

    def get_by_capability(self, capability: str) -> List[Any]:
        ids = self._capability_index.get(capability, [])
        return [self._plugins[pid] for pid in ids if pid in self._plugins]

    def get_by_permission(self, permission: str) -> List[Any]:
        ids = self._permission_index.get(permission, [])
        return [self._plugins[pid] for pid in ids if pid in self._plugins]

    def search(self, query: str = "") -> List[Any]:
        if not query:
            return self.get_all()
        query_lower = query.lower()
        results: List[Any] = []
        for plugin_id, plugin in self._plugins.items():
            if query_lower in plugin_id.lower():
                results.append(plugin)
                continue
            name = getattr(plugin, "name", "")
            if name and query_lower in str(name).lower():
                results.append(plugin)
                continue
            desc = getattr(plugin, "description", "")
            if desc and query_lower in str(desc).lower():
                results.append(plugin)
                continue
        return results

    def count(self) -> int:
        return len(self._plugins)

    def list_ids(self) -> List[str]:
        return list(self._plugins.keys())

    def has(self, plugin_id: str) -> bool:
        return plugin_id in self._plugins

    def update_state(self, plugin_id: str, state: str) -> None:
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            logger.warning("Plugin '%s' not found for state update.", plugin_id)
            return
        self._unindex(plugin_id)
        current_state = getattr(plugin, "state", None)
        if current_state is not None:
            if hasattr(current_state, "value"):
                old_state_str = current_state.value
            else:
                old_state_str = str(current_state)
            lst = self._state_index.get(old_state_str, [])
            if plugin_id in lst:
                lst.remove(plugin_id)
        if hasattr(plugin, "state"):
            try:
                from .models import PluginState
                plugin.state = PluginState(state)
            except (ValueError, TypeError):
                plugin.state = state
        new_state_str = state.value if hasattr(state, "value") else str(state)
        self._state_index[new_state_str].append(plugin_id)
        self._index_capabilities(plugin_id, plugin)
        self._index_permissions(plugin_id, plugin)
        logger.debug("Plugin '%s' state updated to '%s'.", plugin_id, new_state_str)

    def get_stats(self) -> Dict[str, Any]:
        state_counts: Dict[str, int] = defaultdict(int)
        for plugin in self._plugins.values():
            state = getattr(plugin, "state", "unknown")
            state_str = state.value if hasattr(state, "value") else str(state)
            state_counts[state_str] += 1
        return {
            "total": len(self._plugins),
            "by_state": dict(state_counts),
            "by_capability_count": {
                cap: len(ids) for cap, ids in self._capability_index.items()
            },
            "by_permission_count": {
                perm: len(ids) for perm, ids in self._permission_index.items()
            },
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            plugin_id: self._serialize_plugin(plugin)
            for plugin_id, plugin in self._plugins.items()
        }

    def clear(self) -> None:
        self._plugins.clear()
        self._state_index.clear()
        self._capability_index.clear()
        self._permission_index.clear()
        logger.info("Plugin registry cleared.")

    def _index(self, plugin_id: str, plugin: Any) -> None:
        self._index_state(plugin_id, plugin)
        self._index_capabilities(plugin_id, plugin)
        self._index_permissions(plugin_id, plugin)

    def _index_state(self, plugin_id: str, plugin: Any) -> None:
        state = getattr(plugin, "state", None)
        if state is not None:
            state_str = state.value if hasattr(state, "value") else str(state)
            if plugin_id not in self._state_index[state_str]:
                self._state_index[state_str].append(plugin_id)

    def _index_capabilities(self, plugin_id: str, plugin: Any) -> None:
        caps = getattr(plugin, "capabilities", [])
        for cap in caps:
            cap_str = cap.value if hasattr(cap, "value") else str(cap)
            if plugin_id not in self._capability_index[cap_str]:
                self._capability_index[cap_str].append(plugin_id)

    def _index_permissions(self, plugin_id: str, plugin: Any) -> None:
        perms = getattr(plugin, "permissions", [])
        for perm in perms:
            perm_str = perm.value if hasattr(perm, "value") else str(perm)
            if plugin_id not in self._permission_index[perm_str]:
                self._permission_index[perm_str].append(plugin_id)

    def _unindex(self, plugin_id: str) -> None:
        for state_key in list(self._state_index.keys()):
            lst = self._state_index[state_key]
            if plugin_id in lst:
                lst.remove(plugin_id)
                if not lst:
                    del self._state_index[state_key]
        for cap_key in list(self._capability_index.keys()):
            lst = self._capability_index[cap_key]
            if plugin_id in lst:
                lst.remove(plugin_id)
                if not lst:
                    del self._capability_index[cap_key]
        for perm_key in list(self._permission_index.keys()):
            lst = self._permission_index[perm_key]
            if plugin_id in lst:
                lst.remove(plugin_id)
                if not lst:
                    del self._permission_index[perm_key]

    @staticmethod
    def _serialize_plugin(plugin: Any) -> Dict[str, Any]:
        if hasattr(plugin, "to_dict") and callable(plugin.to_dict):
            return plugin.to_dict()
        result: Dict[str, Any] = {}
        for attr in ("id", "name", "version", "state", "description"):
            val = getattr(plugin, attr, None)
            if val is not None:
                if hasattr(val, "value"):
                    val = val.value
                result[attr] = val
        return result