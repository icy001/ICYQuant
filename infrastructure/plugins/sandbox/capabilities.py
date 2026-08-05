"""Sandbox capability guard.

Provides :class:`SandboxCapabilityGuard` for managing the
capabilities exposed by each sandboxed plugin, with thread-safe
tracking and enforcement.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List

from ..exceptions import PluginSandboxViolationError

logger = logging.getLogger(__name__)


class SandboxCapabilityGuard:
    """Manages and enforces sandbox capabilities per plugin.

    Each plugin is mapped to a set of capability strings that
    describe what the plugin is allowed to do within the sandbox.
    All operations are thread-safe via an ``RLock``.

    Attributes:
        _capabilities: Maps plugin_id to a set of capability strings.
        _denied: Maps plugin_id to a set of explicitly denied capabilities.
    """

    def __init__(self) -> None:
        self._capabilities: Dict[str, set[str]] = {}
        self._denied: Dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def grant_capability(self, plugin_id: str, capability: str) -> None:
        """Grant a capability to a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            capability: The capability string to grant.
        """
        with self._lock:
            if plugin_id not in self._capabilities:
                self._capabilities[plugin_id] = set()
            self._capabilities[plugin_id].add(capability)
            logger.debug(
                "Granted capability '%s' to plugin %s",
                capability, plugin_id,
            )

    def revoke_capability(self, plugin_id: str, capability: str) -> None:
        """Revoke a capability from a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            capability: The capability string to revoke.
        """
        with self._lock:
            caps = self._capabilities.get(plugin_id)
            if caps and capability in caps:
                caps.discard(capability)
                logger.debug(
                    "Revoked capability '%s' from plugin %s",
                    capability, plugin_id,
                )

    def check_capability(self, plugin_id: str, capability: str) -> bool:
        """Check whether a plugin holds a specific capability.

        Args:
            plugin_id: Unique identifier for the plugin.
            capability: The capability string to check.

        Returns:
            True if the capability is granted, False otherwise.
        """
        with self._lock:
            denied = self._denied.get(plugin_id, set())
            if capability in denied:
                return False
            caps = self._capabilities.get(plugin_id, set())
            return capability in caps

    def require_capability(self, plugin_id: str, capability: str) -> None:
        """Require a capability, raising if it is not granted.

        Args:
            plugin_id: Unique identifier for the plugin.
            capability: The capability string to require.

        Raises:
            PluginSandboxViolationError: If the capability is not granted.
        """
        if not self.check_capability(plugin_id, capability):
            raise PluginSandboxViolationError(
                f"Plugin '{plugin_id}' requires capability '{capability}' "
                f"but it is not granted"
            )

    def get_capabilities(self, plugin_id: str) -> List[str]:
        """Get all capabilities granted to a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A sorted list of capability strings.
        """
        with self._lock:
            caps = self._capabilities.get(plugin_id, set())
            return sorted(caps)

    def set_capabilities(
        self, plugin_id: str, capabilities: List[str]
    ) -> None:
        """Set the complete capability set for a plugin.

        Replaces any existing capabilities with the provided list.

        Args:
            plugin_id: Unique identifier for the plugin.
            capabilities: List of capability strings to grant.
        """
        with self._lock:
            self._capabilities[plugin_id] = set(capabilities)
            logger.debug(
                "Set %d capabilities for plugin %s",
                len(capabilities), plugin_id,
            )

    def clear_capabilities(self, plugin_id: str) -> None:
        """Clear all capabilities for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
        """
        with self._lock:
            self._capabilities.pop(plugin_id, None)
            self._denied.pop(plugin_id, None)
            logger.debug(
                "Cleared all capabilities for plugin %s", plugin_id
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get capability guard statistics.

        Returns:
            A dictionary with ``total_plugins``, ``total_capabilities``,
            and ``plugins`` (per-plugin summary).
        """
        with self._lock:
            total_caps = sum(len(c) for c in self._capabilities.values())
            plugins = []
            for pid, caps in self._capabilities.items():
                plugins.append({
                    "plugin_id": pid,
                    "capabilities_count": len(caps),
                    "capabilities": sorted(caps),
                })
            return {
                "total_plugins": len(self._capabilities),
                "total_capabilities": total_caps,
                "plugins": plugins,
            }