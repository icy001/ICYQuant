from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from .registry import PluginRegistry
from .events import PluginEventBus

logger = logging.getLogger(__name__)


class PluginMonitoring:
    """Runtime monitoring for plugin metrics and health.

    Collects and exposes metrics about plugin runtime state,
    including active counts, snapshot versions, synchronization
    totals, restart totals, and recovery totals.

    Metrics tracked:
    - ``icyquant_plugin_runtime_total``
    - ``icyquant_plugin_active_total``
    - ``icyquant_plugin_snapshot_version``
    - ``icyquant_plugin_sync_total``
    - ``icyquant_plugin_restart_total``
    - ``icyquant_plugin_recovery_total``

    Usage::

        monitoring = PluginMonitoring(registry)
        await monitoring.start()
        metrics = await monitoring.collect_metrics()
        await monitoring.stop()
    """

    def __init__(
        self,
        registry: Optional[PluginRegistry] = None,
        event_bus: Optional[PluginEventBus] = None,
    ) -> None:
        self._registry = registry or PluginRegistry()
        self._event_bus = event_bus or PluginEventBus()
        self._running = False
        self._task: Optional[asyncio.Task[Any]] = None
        self._interval: float = 30.0
        self._snapshot_version: int = 0
        self._sync_total: int = 0
        self._restart_total: int = 0
        self._recovery_total: int = 0
        self._start_time: Optional[float] = None
        self._plugin_metrics: Dict[str, Dict[str, Any]] = {}

    async def start(self) -> None:
        """Start the monitoring loop.

        Begins periodic metrics collection in the background.
        """
        if self._running:
            logger.debug("Monitoring is already running.")
            return

        self._running = True
        self._start_time = time.monotonic()
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Plugin monitoring started.")

    async def stop(self) -> None:
        """Stop the monitoring loop and collect final metrics."""
        if not self._running:
            logger.debug("Monitoring is not running.")
            return

        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        await self.collect_metrics()
        logger.info("Plugin monitoring stopped.")

    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect all runtime metrics.

        Returns:
            Dictionary with system and per-plugin metrics.
        """
        try:
            snapshot = self._registry.get_stats()
            plugins = self._registry.get_all()

            total = len(plugins)
            active = sum(
                1 for p in plugins
                if hasattr(p, "state") and p.state.value == "running"
            )

            self._snapshot_version += 1

            for plugin in plugins:
                pid = plugin.id
                self._plugin_metrics[pid] = {
                    "id": pid,
                    "state": plugin.state.value if hasattr(plugin, "state") else "unknown",
                    "version": plugin.version if hasattr(plugin, "version") else "",
                    "capabilities": list(plugin.capabilities) if hasattr(plugin, "capabilities") else [],
                    "timestamp": time.monotonic(),
                }

            metrics = {
                "icyquant_plugin_runtime_total": total,
                "icyquant_plugin_active_total": active,
                "icyquant_plugin_snapshot_version": self._snapshot_version,
                "icyquant_plugin_sync_total": self._sync_total,
                "icyquant_plugin_restart_total": self._restart_total,
                "icyquant_plugin_recovery_total": self._recovery_total,
                "timestamp": time.monotonic(),
                "uptime": (
                    time.monotonic() - self._start_time
                    if self._start_time
                    else 0.0
                ),
            }

            logger.debug("Collected metrics: %s", metrics)
            return metrics
        except Exception as e:
            logger.error("Failed to collect metrics: %s", e)
            return {
                "icyquant_plugin_runtime_total": 0,
                "icyquant_plugin_active_total": 0,
                "icyquant_plugin_snapshot_version": self._snapshot_version,
                "icyquant_plugin_sync_total": self._sync_total,
                "icyquant_plugin_restart_total": self._restart_total,
                "icyquant_plugin_recovery_total": self._recovery_total,
                "error": str(e),
            }

    def get_plugin_metrics(self, plugin_id: str) -> Dict[str, Any]:
        """Get metrics for a specific plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            Dictionary with the plugin's metrics, or empty dict if
            not found.
        """
        return dict(self._plugin_metrics.get(plugin_id, {}))

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system-wide metrics snapshot.

        Returns:
            Dictionary with system metrics.
        """
        return {
            "icyquant_plugin_runtime_total": self._registry.count(),
            "icyquant_plugin_active_total": self.get_active_count(),
            "icyquant_plugin_snapshot_version": self._snapshot_version,
            "icyquant_plugin_sync_total": self._sync_total,
            "icyquant_plugin_restart_total": self._restart_total,
            "icyquant_plugin_recovery_total": self._recovery_total,
            "registry": self._registry.get_stats(),
        }

    def get_active_count(self) -> int:
        """Return the number of plugins currently in RUNNING state.

        Returns:
            Count of active plugins.
        """
        try:
            plugins = self._registry.get_all()
            return sum(
                1 for p in plugins
                if hasattr(p, "state") and p.state.value == "running"
            )
        except Exception:
            return 0

    def get_total_count(self) -> int:
        """Return the total number of registered plugins.

        Returns:
            Total plugin count.
        """
        return self._registry.count()

    def get_snapshot_version(self) -> int:
        """Return the current snapshot version number.

        Returns:
            Snapshot version.
        """
        return self._snapshot_version

    def get_sync_total(self) -> int:
        """Return the total number of synchronizations.

        Returns:
            Sync count.
        """
        return self._sync_total

    def get_restart_total(self) -> int:
        """Return the total number of plugin restarts.

        Returns:
            Restart count.
        """
        return self._restart_total

    def get_recovery_total(self) -> int:
        """Return the total number of plugin recovery attempts.

        Returns:
            Recovery count.
        """
        return self._recovery_total

    def is_running(self) -> bool:
        """Check if the monitoring loop is active.

        Returns:
            True if monitoring is running.
        """
        return self._running

    def increment_sync(self) -> None:
        """Increment the synchronization counter."""
        self._sync_total += 1

    def increment_restart(self) -> None:
        """Increment the restart counter."""
        self._restart_total += 1

    def increment_recovery(self) -> None:
        """Increment the recovery counter."""
        self._recovery_total += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive monitoring statistics.

        Returns:
            Dictionary with monitoring state, metrics, and
            per-plugin breakdowns.
        """
        return {
            "running": self._running,
            "uptime": (
                time.monotonic() - self._start_time
                if self._start_time
                else 0.0
            ),
            "snapshot_version": self._snapshot_version,
            "sync_total": self._sync_total,
            "restart_total": self._restart_total,
            "recovery_total": self._recovery_total,
            "active_count": self.get_active_count(),
            "total_count": self.get_total_count(),
            "plugin_metrics": dict(self._plugin_metrics),
        }

    async def _monitor_loop(self) -> None:
        """Background loop that periodically collects metrics."""
        while self._running:
            try:
                await self.collect_metrics()
            except Exception as e:
                logger.error("Error in monitoring loop: %s", e)
            await asyncio.sleep(self._interval)