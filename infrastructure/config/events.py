"""
Configuration Events.

Defines events for configuration changes,
enabling integration with the EventBus.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional


class ConfigurationEvent(str, Enum):
    """
    Configuration event types.

    Events are emitted when configuration
    changes, allowing subscribers to react.
    """

    LOADED = "loaded"
    RELOADED = "reloaded"
    UPDATED = "updated"
    FAILED = "failed"
    ROLLBACK = "rollback"
    VALIDATION_WARNING = "validation_warning"


class ConfigurationEventData:
    """
    Configuration event data.

    Contains the event type, affected keys,
    and metadata for configuration change events.
    """

    def __init__(
        self,
        event_type: ConfigurationEvent,
        affected_keys: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.event_type = event_type
        self.affected_keys = affected_keys or []
        self.metadata = metadata or {}

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_type": self.event_type.value,
            "affected_keys": self.affected_keys,
            "metadata": self.metadata,
        }


class ConfigurationEventBus:
    """
    Simple configuration event bus.

    Allows subscribers to react to configuration
    changes. In production, this will be integrated
    with the main EventBus.
    """

    def __init__(
        self,
    ) -> None:
        self._subscribers: Dict[str, List[Any]] = {}

    def subscribe(
        self,
        event_type: ConfigurationEvent,
        callback: Any,
    ) -> None:
        """
        Subscribe to a configuration event.

        Args:
            event_type: Event type to subscribe to.
            callback: Callback function.
        """
        event_key = event_type.value
        if event_key not in self._subscribers:
            self._subscribers[event_key] = []
        self._subscribers[event_key].append(callback)

    def unsubscribe(
        self,
        event_type: ConfigurationEvent,
        callback: Any,
    ) -> None:
        """Unsubscribe from a configuration event."""
        event_key = event_type.value
        if event_key in self._subscribers:
            try:
                self._subscribers[event_key].remove(callback)
            except ValueError:
                pass

    def publish(
        self,
        event_type: ConfigurationEvent,
        affected_keys: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Publish a configuration event.

        Args:
            event_type: Event type.
            affected_keys: Keys that changed.
            metadata: Additional metadata.
        """
        event_data = ConfigurationEventData(
            event_type=event_type,
            affected_keys=affected_keys,
            metadata=metadata,
        )

        event_key = event_type.value
        subscribers = self._subscribers.get(event_key, [])
        for callback in subscribers:
            try:
                callback(event_data)
            except Exception:
                pass

    def get_subscriber_count(
        self,
        event_type: Optional[ConfigurationEvent] = None,
    ) -> int:
        """Get subscriber count."""
        if event_type:
            return len(self._subscribers.get(event_type.value, []))
        return sum(len(v) for v in self._subscribers.values())

    def clear(
        self,
    ) -> None:
        """Clear all subscribers."""
        self._subscribers.clear()
