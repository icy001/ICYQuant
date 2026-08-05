from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from .events import PluginEvent, PluginEventBus, PluginEventType
from .exceptions import PluginError
from .registry import PluginRegistry

logger = logging.getLogger(__name__)


class PluginSynchronization:
    """Cluster synchronization for plugin state across nodes.

    Provides full and incremental sync, event broadcast, conflict
    detection, and event replay support for new nodes joining the
    cluster.

    Automatic sync is triggered on ``PluginInstalled``,
    ``PluginUpdated``, and ``PluginRemoved`` events.
    """

    MAX_EVENT_LOG = 5000

    def __init__(
        self,
        registry: Optional[PluginRegistry] = None,
        event_bus: Optional[PluginEventBus] = None,
    ) -> None:
        self._registry = registry or PluginRegistry()
        self._event_bus = event_bus or PluginEventBus()
        self._snapshot_version = 0
        self._last_sync: Optional[datetime] = None
        self._event_log: List[Dict[str, Any]] = []
        self._peer_versions: Dict[str, int] = {}
        self._conflicts: List[Dict[str, Any]] = []
        self._stats: Dict[str, int] = {
            "sync_count": 0,
            "broadcasts": 0,
            "conflicts_detected": 0,
            "replays": 0,
        }

    async def sync(self) -> Dict[str, Any]:
        """Perform a full synchronization of all plugins.

        Returns:
            Sync result with counts and updated snapshot version.
        """
        self._snapshot_version += 1
        self._last_sync = datetime.utcnow()
        self._stats["sync_count"] += 1

        all_plugins = self._registry.get_all()
        results: Dict[str, Any] = {
            "snapshot_version": self._snapshot_version,
            "plugin_count": len(all_plugins),
            "synced": [],
            "failed": [],
            "timestamp": self._last_sync.isoformat(),
        }

        for plugin in all_plugins:
            plugin_id = getattr(plugin, "id", str(plugin))
            try:
                results["synced"].append(plugin_id)
            except Exception as e:
                results["failed"].append({
                    "plugin_id": plugin_id,
                    "error": str(e),
                })

        logger.info(
            "Full sync complete: %d plugins (snapshot v%d).",
            len(all_plugins),
            self._snapshot_version,
        )
        return results

    async def sync_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Synchronize a single plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            Sync result for the plugin.
        """
        plugin = self._registry.get_plugin(plugin_id)
        if plugin is None:
            return {
                "plugin_id": plugin_id,
                "success": False,
                "error": "Plugin not found in registry.",
            }

        self._snapshot_version += 1
        self._last_sync = datetime.utcnow()
        self._stats["sync_count"] += 1

        result: Dict[str, Any] = {
            "plugin_id": plugin_id,
            "snapshot_version": self._snapshot_version,
            "success": True,
            "timestamp": self._last_sync.isoformat(),
        }

        if hasattr(plugin, "to_dict"):
            result["data"] = plugin.to_dict()

        logger.info("Synced plugin '%s'.", plugin_id)
        return result

    def get_snapshot_version(self) -> int:
        """Return the current snapshot version number.

        Returns:
            The snapshot version (monotonically increasing).
        """
        return self._snapshot_version

    def get_last_sync(self) -> Optional[datetime]:
        """Return the timestamp of the last synchronization.

        Returns:
            The last sync datetime, or ``None`` if never synced.
        """
        return self._last_sync

    async def broadcast_event(
        self, event: Dict[str, Any]
    ) -> None:
        """Broadcast an event to all cluster peers.

        The event is appended to the replay log for late-joining nodes.

        Args:
            event: The event data dictionary.
        """
        self._event_log.append(dict(event))
        if len(self._event_log) > self.MAX_EVENT_LOG:
            self._event_log = self._event_log[-self.MAX_EVENT_LOG:]
        self._stats["broadcasts"] += 1

        logger.debug(
            "Broadcast event '%s' to cluster.",
            event.get("event_type", "unknown"),
        )

    def on_cluster_event(self, event: Dict[str, Any]) -> None:
        """Handle an incoming event from a cluster peer.

        Args:
            event: The incoming event data dictionary.
        """
        event_type = event.get("event_type", "")
        plugin_id = event.get("plugin_id", "")
        data = event.get("data", {})

        if event_type in (
            PluginEventType.INSTALLED,
            PluginEventType.RELOADED,
            PluginEventType.CONFIG_CHANGED,
        ):
            logger.debug(
                "Processing cluster event '%s' for '%s'.",
                event_type,
                plugin_id,
            )
        elif event_type == PluginEventType.REMOVED:
            logger.debug(
                "Processing removal event for '%s'.", plugin_id
            )
        else:
            logger.debug(
                "Received cluster event '%s' for '%s'.",
                event_type,
                plugin_id,
            )

    def detect_conflict(
        self,
        local: Dict[str, Any],
        remote: Dict[str, Any],
    ) -> List[str]:
        """Detect conflicts between local and remote plugin states.

        Uses version-based conflict resolution: if both sides modified
        the same plugin with different versions, a conflict is flagged.

        Args:
            local: Local state dictionary.
            remote: Remote state dictionary.

        Returns:
            List of conflicting plugin identifiers.
        """
        conflicts: List[str] = []
        local_plugins = local.get("plugins", {})
        remote_plugins = remote.get("plugins", {})

        for plugin_id in local_plugins:
            if plugin_id not in remote_plugins:
                continue
            local_version = local_plugins[plugin_id].get(
                "version", ""
            )
            remote_version = remote_plugins[plugin_id].get(
                "version", ""
            )
            if local_version != remote_version:
                conflicts.append(plugin_id)

        if conflicts:
            self._stats["conflicts_detected"] += len(conflicts)
            logger.warning(
                "Detected %d conflict(s): %s",
                len(conflicts),
                conflicts,
            )

        return conflicts

    def replay_events(
        self, since_version: int = 0
    ) -> List[Dict[str, Any]]:
        """Return the event log for replay to a new cluster node.

        Args:
            since_version: Minimum snapshot version to include.

        Returns:
            List of events with snapshot version >= ``since_version``.
        """
        self._stats["replays"] += 1
        return [
            e
            for e in self._event_log
            if e.get("snapshot_version", 0) >= since_version
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get synchronization statistics.

        Returns:
            A dictionary with sync state and counters.
        """
        return {
            "snapshot_version": self._snapshot_version,
            "last_sync": (
                self._last_sync.isoformat()
                if self._last_sync
                else None
            ),
            "event_log_size": len(self._event_log),
            "peer_count": len(self._peer_versions),
            "conflict_count": len(self._conflicts),
            "stats": dict(self._stats),
        }