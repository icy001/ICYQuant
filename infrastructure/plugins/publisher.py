from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .events import PluginEvent, PluginEventBus, PluginEventType

logger = logging.getLogger(__name__)


class PluginPublisher:
    """Publishes plugin events to the ICYQuant EventBus.

    Provides a high-level API for emitting lifecycle events such as
    installation, updates, removal, start, stop, reload, rollback,
    and recovery.

    Usage::

        publisher = PluginPublisher(event_bus)
        await publisher.publish_plugin_event("my_plugin", "plugin.started")
    """

    EVENT_INSTALLED = "PluginInstalled"
    EVENT_UPDATED = "PluginUpdated"
    EVENT_REMOVED = "PluginRemoved"
    EVENT_STARTED = "PluginStarted"
    EVENT_STOPPED = "PluginStopped"
    EVENT_RELOADED = "PluginReloaded"
    EVENT_ROLLBACK = "PluginRollback"
    EVENT_RECOVERED = "PluginRecovered"

    _EVENT_MAP: Dict[str, str] = {
        EVENT_INSTALLED: PluginEventType.INSTALLED,
        EVENT_UPDATED: PluginEventType.CONFIG_CHANGED,
        EVENT_REMOVED: PluginEventType.REMOVED,
        EVENT_STARTED: PluginEventType.STARTED,
        EVENT_STOPPED: PluginEventType.STOPPED,
        EVENT_RELOADED: PluginEventType.RELOADED,
        EVENT_ROLLBACK: PluginEventType.CONFIG_CHANGED,
        EVENT_RECOVERED: PluginEventType.FAILED,
    }

    def __init__(self, event_bus: Optional[PluginEventBus] = None) -> None:
        self._event_bus = event_bus or PluginEventBus()
        self._publishers: set[str] = set()
        self._publish_count: int = 0
        self._failed_count: int = 0
        self._event_counts: Dict[str, int] = {}

    @property
    def event_bus(self) -> PluginEventBus:
        return self._event_bus

    async def publish(
        self, event_type: str, data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Publish a generic event to the event bus.

        Args:
            event_type: The event type string.
            data: Optional event data dictionary.
        """
        try:
            event = PluginEvent(
                event_type=event_type,
                plugin_id="publisher",
                data=data or {},
            )
            await self._event_bus.publish(event)
            self._publish_count += 1
            self._event_counts[event_type] = (
                self._event_counts.get(event_type, 0) + 1
            )
            logger.debug("Published event '%s'.", event_type)
        except Exception as e:
            self._failed_count += 1
            logger.error("Failed to publish event '%s': %s", event_type, e)

    async def publish_plugin_event(
        self,
        plugin_id: str,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish a plugin-specific event to the event bus.

        The event_type is mapped to the corresponding PluginEventType
        constant when possible.

        Args:
            plugin_id: The plugin identifier.
            event_type: The event type (e.g. ``PluginStarted``).
            data: Optional event data dictionary.
        """
        mapped_type = self._EVENT_MAP.get(event_type, event_type)
        try:
            event = PluginEvent(
                event_type=mapped_type,
                plugin_id=plugin_id,
                data=data or {},
            )
            await self._event_bus.publish(event)
            self._publish_count += 1
            self._event_counts[event_type] = (
                self._event_counts.get(event_type, 0) + 1
            )
            logger.info(
                "Published '%s' for plugin '%s'.", event_type, plugin_id
            )
        except Exception as e:
            self._failed_count += 1
            logger.error(
                "Failed to publish '%s' for plugin '%s': %s",
                event_type,
                plugin_id,
                e,
            )

    async def broadcast(self, event: Dict[str, Any]) -> None:
        """Broadcast an event dictionary to all subscribers.

        Args:
            event: A dictionary with ``event_type``, ``plugin_id``,
                   and optional ``data`` keys.
        """
        try:
            event_obj = PluginEvent(
                event_type=str(event.get("event_type", "unknown")),
                plugin_id=str(event.get("plugin_id", "broadcast")),
                data=event.get("data", {}) or {},
            )
            await self._event_bus.publish(event_obj)
            self._publish_count += 1
            event_type = event_obj.event_type
            self._event_counts[event_type] = (
                self._event_counts.get(event_type, 0) + 1
            )
            logger.debug("Broadcast event '%s'.", event_type)
        except Exception as e:
            self._failed_count += 1
            logger.error("Failed to broadcast event: %s", e)

    def register_publisher(self, plugin_id: str) -> None:
        """Register a plugin as an event publisher.

        Args:
            plugin_id: The plugin identifier to register.
        """
        self._publishers.add(plugin_id)
        logger.debug("Registered publisher '%s'.", plugin_id)

    def get_publishers(self) -> List[str]:
        """Return the list of registered publisher plugin IDs.

        Returns:
            Sorted list of publisher identifiers.
        """
        return sorted(self._publishers)

    def get_stats(self) -> Dict[str, Any]:
        """Get publisher statistics.

        Returns:
            Dictionary with publish counts, failure counts,
            registered publishers, and per-event-type counts.
        """
        return {
            "total_published": self._publish_count,
            "total_failed": self._failed_count,
            "registered_publishers": len(self._publishers),
            "publishers": self.get_publishers(),
            "event_counts": dict(self._event_counts),
            "event_bus": self._event_bus.get_stats(),
        }