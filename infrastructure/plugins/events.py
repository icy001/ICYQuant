from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
import inspect
import logging

logger = logging.getLogger(__name__)


class PluginEventType:
    """String constants identifying plugin lifecycle events."""

    INSTALLED = "plugin.installed"
    LOADED = "plugin.loaded"
    INITIALIZED = "plugin.initialized"
    STARTED = "plugin.started"
    STOPPED = "plugin.stopped"
    UNLOADED = "plugin.unloaded"
    RELOADED = "plugin.reloaded"
    FAILED = "plugin.failed"
    REMOVED = "plugin.removed"
    CONFIG_CHANGED = "plugin.config_changed"


@dataclass
class PluginEvent:
    event_type: str
    plugin_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "plugin_id": self.plugin_id,
            "data": dict(self.data),
            "timestamp": self.timestamp.isoformat(),
        }


class PluginEventBus:
    """Event bus for plugin lifecycle events."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable]] = {}
        self._global_subscribers: List[Callable] = []
        self._history: List[PluginEvent] = []
        self._stats: Dict[str, int] = {}
        self._max_history = 1000

    async def publish(self, event: PluginEvent) -> int:
        """Publish an event; return the number of subscribers notified."""
        count = 0
        self._history.append(event)
        if len(self._history) > self._max_history:
            del self._history[: len(self._history) - self._max_history]
        self._stats[event.event_type] = self._stats.get(event.event_type, 0) + 1

        handlers: List[Callable] = []
        handlers.extend(self._subscribers.get(event.event_type, []))
        handlers.extend(self._global_subscribers)

        for handler in handlers:
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
                count += 1
            except Exception:
                logger.exception("Event subscriber for %s failed", event.event_type)
        return count

    async def subscribe(self, event_type: str, handler: Callable) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    async def subscribe_all(self, handler: Callable) -> None:
        self._global_subscribers.append(handler)

    def get_history(self, plugin_id: str = None, limit: int = 100) -> List[PluginEvent]:
        events = self._history
        if plugin_id is not None:
            events = [e for e in events if e.plugin_id == plugin_id]
        if limit is None or limit < 0:
            return list(events)
        if limit == 0:
            return []
        return list(events[-limit:])

    def get_stats(self) -> Dict[str, Any]:
        subscriber_count = sum(len(v) for v in self._subscribers.values()) + len(
            self._global_subscribers
        )
        return {
            "total_events": sum(self._stats.values()),
            "by_type": dict(self._stats),
            "subscriber_count": subscriber_count,
            "history_size": len(self._history),
        }

    async def shutdown(self) -> None:
        self._subscribers.clear()
        self._global_subscribers.clear()
        self._history.clear()
        self._stats.clear()
