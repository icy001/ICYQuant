from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from .events import PluginEvent, PluginEventBus, PluginEventType

logger = logging.getLogger(__name__)

PREDEFINED_SUBSCRIBERS = frozenset({
    "oms",
    "risk_engine",
    "execution_engine",
    "gateway",
    "strategy_engine",
    "research",
    "ai_platform",
})


class PluginSubscriber:
    """Subscribes to plugin events and dispatches to registered callbacks.

    Supports predefined subscriber types (OMS, Risk Engine, etc.)
    and allows custom callback registration. Each subscriber type has
    a default callback registration mechanism.

    Usage::

        subscriber = PluginSubscriber(event_bus)
        await subscriber.subscribe("oms", my_oms_callback)
        subscriber.notify("plugin.started", {"plugin_id": "my_plugin"})
    """

    def __init__(self, event_bus: Optional[PluginEventBus] = None) -> None:
        self._event_bus = event_bus or PluginEventBus()
        self._subscribers: Dict[str, List[Callable]] = {}
        self._notification_count: int = 0
        self._failed_count: int = 0
        self._notified_events: Dict[str, int] = {}

    @property
    def event_bus(self) -> PluginEventBus:
        return self._event_bus

    async def subscribe(
        self, plugin_id: str, callback: Callable
    ) -> None:
        """Register a callback for a plugin subscriber.

        If the subscriber is a predefined type, the callback is
        registered with the event bus for all plugin events.

        Args:
            plugin_id: The subscriber identifier (e.g. ``oms``).
            callback: The callable to invoke when events arrive.
        """
        if plugin_id not in self._subscribers:
            self._subscribers[plugin_id] = []

        self._subscribers[plugin_id].append(callback)

        if plugin_id in PREDEFINED_SUBSCRIBERS:
            await self._event_bus.subscribe_all(callback)
            logger.info(
                "Predefined subscriber '%s' registered for all events.",
                plugin_id,
            )
        else:
            for event_type in (
                PluginEventType.STARTED,
                PluginEventType.STOPPED,
                PluginEventType.RELOADED,
                PluginEventType.FAILED,
                PluginEventType.INSTALLED,
                PluginEventType.REMOVED,
            ):
                await self._event_bus.subscribe(event_type, callback)
            logger.info(
                "Subscriber '%s' registered for lifecycle events.",
                plugin_id,
            )

    async def unsubscribe(self, plugin_id: str) -> None:
        """Remove all callbacks for a subscriber.

        Args:
            plugin_id: The subscriber identifier to remove.
        """
        callbacks = self._subscribers.pop(plugin_id, None)
        if callbacks is None:
            logger.debug(
                "No subscriber found for '%s'.", plugin_id
            )
            return

        remaining_global = [
            cb
            for sid, cbs in self._subscribers.items()
            if sid in PREDEFINED_SUBSCRIBERS
            for cb in cbs
        ]

        global_subs = self._event_bus._global_subscribers
        to_remove = [cb for cb in callbacks if cb in global_subs]
        for cb in to_remove:
            global_subs.remove(cb)

        for cb in callbacks:
            for event_type, handler_list in self._event_bus._subscribers.items():
                if cb in handler_list:
                    handler_list.remove(cb)

        logger.info("Unsubscribed '%s'.", plugin_id)

    def get_subscribers(self) -> Dict[str, List[Callable]]:
        """Return all registered subscribers and their callbacks.

        Returns:
            Dictionary mapping subscriber IDs to lists of callbacks.
        """
        return {
            sid: list(cbs) for sid, cbs in self._subscribers.items()
        }

    def notify(
        self, event_type: str, data: Dict[str, Any]
    ) -> None:
        """Notify all subscribers of an event.

        Args:
            event_type: The event type string.
            data: The event data dictionary.
        """
        plugin_id = str(data.get("plugin_id", "unknown"))
        event = PluginEvent(
            event_type=event_type,
            plugin_id=plugin_id,
            data=data,
        )

        notified = 0
        for sid, callbacks in self._subscribers.items():
            for callback in callbacks:
                try:
                    result = callback(event)
                    if hasattr(result, "__await__"):
                        import asyncio
                        asyncio.get_event_loop().create_task(result)
                    notified += 1
                except Exception as e:
                    self._failed_count += 1
                    logger.error(
                        "Callback failed for subscriber '%s': %s",
                        sid,
                        e,
                    )

        self._notification_count += notified
        self._notified_events[event_type] = (
            self._notified_events.get(event_type, 0) + 1
        )
        logger.debug(
            "Notified %d subscribers for '%s'.", notified, event_type
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get subscriber statistics.

        Returns:
            Dictionary with subscriber counts, notification counts,
            and per-event-type notification counts.
        """
        return {
            "total_subscribers": len(self._subscribers),
            "subscriber_ids": sorted(self._subscribers.keys()),
            "predefined_count": len(
                set(self._subscribers.keys()) & PREDEFINED_SUBSCRIBERS
            ),
            "total_notifications": self._notification_count,
            "total_failed": self._failed_count,
            "notified_events": dict(self._notified_events),
            "event_bus": self._event_bus.get_stats(),
        }