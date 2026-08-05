from __future__ import annotations

import importlib
import logging
import os
from typing import Any, Dict, List, Optional

from .models import PluginState
from .registry import PluginRegistry

logger = logging.getLogger(__name__)


class RuntimeDiscovery:
    """Discovers plugins at runtime from paths, registry, and the
    current execution environment.

    Maps plugin states to the standard lifecycle:
    ``REGISTERED`` → ``LOADED`` → ``INITIALIZED`` → ``RUNNING``
    → ``STOPPED``.
    """

    def __init__(
        self,
        registry: Optional[PluginRegistry] = None,
    ) -> None:
        self._registry = registry or PluginRegistry()
        self._discovery_cache: Dict[str, Any] = {}

    def discover_plugins(
        self, paths: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Discover plugins from filesystem paths.

        Each path is scanned for Python modules that expose a
        ``Plugin`` subclass.

        Args:
            paths: File-system directories to scan. Defaults to
                ``["plugins"]``.

        Returns:
            List of discovered plugin metadata dictionaries.
        """
        if paths is None:
            paths = ["plugins"]

        discovered: List[Dict[str, Any]] = []

        for base_path in paths:
            if not os.path.isdir(base_path):
                logger.debug(
                    "Discovery path does not exist: '%s'.",
                    base_path,
                )
                continue

            for entry in os.listdir(base_path):
                full_path = os.path.join(base_path, entry)
                if not os.path.isdir(full_path):
                    continue
                init_file = os.path.join(full_path, "__init__.py")
                if not os.path.isfile(init_file):
                    continue

                plugin_info = self._inspect_package(full_path, entry)
                if plugin_info is not None:
                    discovered.append(plugin_info)
                    self._discovery_cache[entry] = plugin_info

        logger.info(
            "Discovered %d plugin(s) from %d path(s).",
            len(discovered),
            len(paths),
        )
        return discovered

    def discover_from_registry(self) -> List[Dict[str, Any]]:
        """Discover plugins already registered in the plugin registry.

        Returns:
            List of registered plugin data dictionaries.
        """
        all_plugins = self._registry.get_all()
        result: List[Dict[str, Any]] = []
        for plugin in all_plugins:
            if hasattr(plugin, "to_dict"):
                result.append(plugin.to_dict())
            else:
                result.append({
                    "id": str(plugin),
                    "state": "unknown",
                })
        return result

    def get_running_plugins(self) -> List[Dict[str, Any]]:
        """Return plugins currently in the ``RUNNING`` state.

        Returns:
            List of running plugin data dictionaries.
        """
        running = self._registry.get_by_state(PluginState.RUNNING.value)
        result: List[Dict[str, Any]] = []
        for plugin in running:
            if hasattr(plugin, "to_dict"):
                result.append(plugin.to_dict())
            else:
                result.append({
                    "id": str(plugin),
                    "state": PluginState.RUNNING.value,
                })
        return result

    def get_plugin_graph(self) -> Dict[str, Any]:
        """Build the plugin dependency graph.

        Returns:
            A dictionary mapping each plugin ID to its list of
            dependency IDs.
        """
        graph: Dict[str, Any] = {}
        all_plugins = self._registry.get_all()
        for plugin in all_plugins:
            plugin_id = getattr(plugin, "id", str(plugin))
            deps = getattr(plugin, "dependencies", [])
            graph[plugin_id] = list(deps)
        return graph

    def get_runtime_topology(self) -> Dict[str, Any]:
        """Build the full runtime topology of the plugin framework.

        Returns:
            Topology dictionary with plugins, states, dependencies,
            and capability information.
        """
        all_plugins = self._registry.get_all()

        by_state: Dict[str, List[str]] = {}
        capabilities: Dict[str, List[str]] = {}
        permissions: Dict[str, List[str]] = {}

        for plugin in all_plugins:
            plugin_id = getattr(plugin, "id", str(plugin))
            state = getattr(plugin, "state", None)
            state_str = (
                state.value
                if hasattr(state, "value")
                else str(state)
            )
            by_state.setdefault(state_str, []).append(plugin_id)

            caps = getattr(plugin, "capabilities", [])
            for cap in caps:
                cap_str = (
                    cap.value if hasattr(cap, "value") else str(cap)
                )
                capabilities.setdefault(cap_str, []).append(plugin_id)

            perms = getattr(plugin, "permissions", [])
            for perm in perms:
                perm_str = (
                    perm.value if hasattr(perm, "value") else str(perm)
                )
                permissions.setdefault(perm_str, []).append(plugin_id)

        return {
            "total_plugins": len(all_plugins),
            "by_state": by_state,
            "dependencies": self.get_plugin_graph(),
            "capabilities": capabilities,
            "permissions": permissions,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get discovery statistics.

        Returns:
            A dictionary with discovery counts and cached entries.
        """
        return {
            "cached_discoveries": len(self._discovery_cache),
            "registry_plugins": self._registry.count(),
            "running_count": len(self.get_running_plugins()),
            "topology": self.get_runtime_topology(),
        }

    @staticmethod
    def _inspect_package(
        path: str, name: str
    ) -> Optional[Dict[str, Any]]:
        """Inspect a package directory for plugin metadata.

        Args:
            path: Absolute path to the package directory.
            name: Package name.

        Returns:
            Plugin metadata dictionary, or ``None`` if not a valid
            plugin package.
        """
        manifest_path = os.path.join(path, "manifest.json")
        if os.path.isfile(manifest_path):
            try:
                import json

                with open(manifest_path, "r", encoding="utf-8") as fh:
                    manifest = json.load(fh)
                return {
                    "id": manifest.get("id", name),
                    "name": manifest.get("name", name),
                    "version": manifest.get("version", "0.0.0"),
                    "state": PluginState.REGISTERED.value,
                    "source": manifest_path,
                }
            except Exception:
                logger.debug(
                    "Failed to parse manifest for '%s'.", name
                )

        return None