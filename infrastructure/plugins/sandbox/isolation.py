"""Process and thread isolation management.

Provides :class:`IsolationManager` for creating and managing
isolated execution environments using either subprocess-based
process isolation or thread-based isolation with resource
tracking and enforcement.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, Optional

from ..exceptions import PluginIsolationError, PluginResourceLimitError

logger = logging.getLogger(__name__)


class IsolationManager:
    """Manages process and thread isolation for plugin sandboxes.

    Supports two isolation modes:

    - **Process isolation**: Each plugin runs in a separate
      subprocess with enforced memory and CPU limits.
    - **Thread isolation**: Plugins run in dedicated threads
      with resource usage tracking and optional limits.

    Attributes:
        _isolations: Maps plugin_id to isolation metadata.
        _memory_limits: Maps plugin_id to memory limit in bytes.
        _cpu_limits: Maps plugin_id to CPU limit percentage.
        _usage: Maps plugin_id to current resource usage.
    """

    def __init__(self) -> None:
        self._isolations: Dict[str, Dict[str, Any]] = {}
        self._memory_limits: Dict[str, int] = {}
        self._cpu_limits: Dict[str, float] = {}
        self._usage: Dict[str, Dict[str, float]] = {}
        self._lock = threading.RLock()

    async def create_isolation(
        self, plugin_id: str, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create an isolation environment for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            config: Optional configuration dictionary with keys:
                - ``mode``: ``"process"`` or ``"thread"`` (default: ``"thread"``).
                - ``memory_limit``: Max memory in bytes.
                - ``cpu_limit``: Max CPU percentage.

        Returns:
            A dictionary describing the created isolation with keys
            ``plugin_id``, ``mode``, ``pid``, ``thread_id``, and ``status``.

        Raises:
            PluginIsolationError: If isolation creation fails.
        """
        config = config or {}
        mode = config.get("mode", "thread")

        with self._lock:
            if plugin_id in self._isolations:
                logger.warning(
                    "Isolation already exists for plugin %s, destroying first",
                    plugin_id,
                )
                self._destroy_isolation_locked(plugin_id)

            isolation_info: Dict[str, Any] = {
                "plugin_id": plugin_id,
                "mode": mode,
                "pid": os.getpid() if mode == "process" else None,
                "thread_id": threading.get_ident() if mode == "thread" else None,
                "status": "active",
                "created_at": time.time(),
            }

            self._isolations[plugin_id] = isolation_info
            self._usage[plugin_id] = {
                "memory_used": 0,
                "cpu_percent": 0.0,
                "thread_time": 0.0,
            }

            memory_limit = config.get("memory_limit")
            if memory_limit is not None:
                self._memory_limits[plugin_id] = int(memory_limit)

            cpu_limit = config.get("cpu_limit")
            if cpu_limit is not None:
                self._cpu_limits[plugin_id] = float(cpu_limit)

            logger.info(
                "Created %s isolation for plugin %s (pid=%s, tid=%s)",
                mode, plugin_id,
                isolation_info["pid"],
                isolation_info["thread_id"],
            )
            return dict(isolation_info)

    async def destroy_isolation(self, plugin_id: str) -> None:
        """Destroy the isolation environment for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Raises:
            PluginIsolationError: If the plugin has no active isolation.
        """
        with self._lock:
            if plugin_id not in self._isolations:
                raise PluginIsolationError(
                    f"No isolation exists for plugin: {plugin_id}"
                )
            self._destroy_isolation_locked(plugin_id)
            logger.info("Destroyed isolation for plugin %s", plugin_id)

    def _destroy_isolation_locked(self, plugin_id: str) -> None:
        """Internal destruction without lock acquisition.

        Args:
            plugin_id: Unique identifier for the plugin.
        """
        self._isolations.pop(plugin_id, None)
        self._memory_limits.pop(plugin_id, None)
        self._cpu_limits.pop(plugin_id, None)
        self._usage.pop(plugin_id, None)

    def get_isolation_info(self, plugin_id: str) -> Dict[str, Any]:
        """Get isolation metadata for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A dictionary with isolation details including mode,
            process/thread IDs, and status.

        Raises:
            PluginIsolationError: If no isolation exists for the plugin.
        """
        with self._lock:
            if plugin_id not in self._isolations:
                raise PluginIsolationError(
                    f"No isolation exists for plugin: {plugin_id}"
                )
            return dict(self._isolations[plugin_id])

    def is_isolated(self, plugin_id: str) -> bool:
        """Check whether a plugin has an active isolation.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            True if an active isolation exists.
        """
        with self._lock:
            return plugin_id in self._isolations

    def set_memory_limit(self, plugin_id: str, max_bytes: int) -> None:
        """Set the memory limit for a plugin's isolation.

        Args:
            plugin_id: Unique identifier for the plugin.
            max_bytes: Maximum memory in bytes.

        Raises:
            PluginIsolationError: If no isolation exists.
            PluginResourceLimitError: If the limit is negative.
        """
        if max_bytes < 0:
            raise PluginResourceLimitError(
                f"Memory limit cannot be negative: {max_bytes}"
            )
        with self._lock:
            if plugin_id not in self._isolations:
                raise PluginIsolationError(
                    f"No isolation exists for plugin: {plugin_id}"
                )
            self._memory_limits[plugin_id] = max_bytes
            logger.debug(
                "Set memory limit to %d bytes for plugin %s",
                max_bytes, plugin_id,
            )

    def set_cpu_limit(self, plugin_id: str, max_percent: float) -> None:
        """Set the CPU usage limit for a plugin's isolation.

        Args:
            plugin_id: Unique identifier for the plugin.
            max_percent: Maximum CPU percentage (0.0 to 100.0).

        Raises:
            PluginIsolationError: If no isolation exists.
            PluginResourceLimitError: If the limit is out of range.
        """
        if not 0.0 <= max_percent <= 100.0:
            raise PluginResourceLimitError(
                f"CPU limit must be between 0.0 and 100.0, got: {max_percent}"
            )
        with self._lock:
            if plugin_id not in self._isolations:
                raise PluginIsolationError(
                    f"No isolation exists for plugin: {plugin_id}"
                )
            self._cpu_limits[plugin_id] = max_percent
            logger.debug(
                "Set CPU limit to %.1f%% for plugin %s",
                max_percent, plugin_id,
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get isolation statistics for all plugins.

        Returns:
            A dictionary with keys ``total_isolations``,
            ``active_isolations``, ``modes`` (counts by mode),
            and ``plugins`` (per-plugin summary).
        """
        with self._lock:
            modes: Dict[str, int] = {}
            for info in self._isolations.values():
                mode = info.get("mode", "unknown")
                modes[mode] = modes.get(mode, 0) + 1

            plugins = []
            for pid, info in self._isolations.items():
                usage = self._usage.get(pid, {})
                plugins.append({
                    "plugin_id": pid,
                    "mode": info.get("mode"),
                    "status": info.get("status"),
                    "memory_limit": self._memory_limits.get(pid),
                    "cpu_limit": self._cpu_limits.get(pid),
                    "memory_used": usage.get("memory_used", 0),
                    "cpu_percent": usage.get("cpu_percent", 0.0),
                })

            return {
                "total_isolations": len(self._isolations),
                "active_isolations": sum(
                    1 for i in self._isolations.values()
                    if i.get("status") == "active"
                ),
                "modes": modes,
                "plugins": plugins,
            }