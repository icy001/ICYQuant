"""
Configuration event publisher.

Publishes configuration change events to subscribers
via the EventBus. Supports multiple event types:
- Snapshot Created
- Snapshot Activated
- Snapshot Rollback
- Configuration Reloaded
- Validation Failed
"""

from __future__ import annotations

import threading
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..events import ConfigurationEvent, ConfigurationEventBus, ConfigurationEventData


class DynamicEvent(str, Enum):
    """Dynamic configuration event types."""

    SNAPSHOT_CREATED = "snapshot_created"
    SNAPSHOT_ACTIVATED = "snapshot_activated"
    SNAPSHOT_ROLLED_BACK = "snapshot_rolled_back"
    CONFIG_RELOADED = "config_reloaded"
    RELOAD_SUCCEEDED = "reload_succeeded"
    RELOAD_FAILED = "reload_failed"
    VALIDATION_FAILED = "validation_failed"
    CONFIG_CHANGED = "config_changed"
    SUBSCRIBER_ADDED = "subscriber_added"
    SUBSCRIBER_REMOVED = "subscriber_removed"


class ConfigurationEventPublisher:
    """
    Publishes configuration change events.

    Bridges the dynamic configuration system with
    the EventBus, ensuring all interested components
    are notified of configuration changes.

    Supports:
    - Event filtering by type
    - Targeted subscriber notifications
    - Event batching
    - Synchronous and asynchronous dispatch

    Usage:
        publisher = ConfigurationEventPublisher()
        publisher.on(DynamicEvent.CONFIG_RELOADED, lambda e: print(e))
        publisher.publish(DynamicEvent.CONFIG_RELOADED, data=config)
    """

    def __init__(
        self,
        event_bus: Optional[ConfigurationEventBus] = None,
    ) -> None:
        """
        Initialize event publisher.

        Args:
            event_bus: EventBus instance (uses default if None).
        """
        self._event_bus = event_bus or ConfigurationEventBus()
        self._listeners: Dict[str, List[Callable]] = {}
        self._event_history: List[Dict[str, Any]] = []
        self._max_history = 1000
        self._lock = threading.Lock()

    @property
    def event_bus(
        self,
    ) -> ConfigurationEventBus:
        """Get underlying event bus."""
        return self._event_bus

    def on(
        self,
        event_type: DynamicEvent,
        callback: Callable,
    ) -> None:
        """
        Subscribe to a dynamic event.

        Args:
            event_type: Event type to subscribe to.
            callback: Callback function.
        """
        with self._lock:
            event_key = event_type.value
            if event_key not in self._listeners:
                self._listeners[event_key] = []
            self._listeners[event_key].append(callback)

    def off(
        self,
        event_type: DynamicEvent,
        callback: Callable,
    ) -> None:
        """
        Unsubscribe from a dynamic event.

        Args:
            event_type: Event type.
            callback: Callback to remove.
        """
        with self._lock:
            event_key = event_type.value
            if event_key in self._listeners:
                try:
                    self._listeners[event_key].remove(callback)
                except ValueError:
                    pass

    def publish(
        self,
        event_type: DynamicEvent,
        data: Optional[Dict[str, Any]] = None,
        source: str = "dynamic",
        affected_keys: Optional[List[str]] = None,
    ) -> None:
        """
        Publish a configuration change event.

        Args:
            event_type: Event type.
            data: Event data payload.
            source: Source of the event.
            affected_keys: Keys affected by the change.
        """
        event_data = {
            "event_type": event_type.value,
            "source": source,
            "data": data or {},
            "affected_keys": affected_keys or [],
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Store in history
        with self._lock:
            self._event_history.append(event_data)
            if len(self._event_history) > self._max_history:
                self._event_history.pop(0)

        # Notify direct listeners
        listeners = self._listeners.get(event_type.value, [])
        for callback in listeners:
            try:
                callback(event_data)
            except Exception:
                pass

        # Also publish to EventBus for integration
        self._publish_to_event_bus(event_type, event_data)

    def _publish_to_event_bus(
        self,
        event_type: DynamicEvent,
        event_data: Dict[str, Any],
    ) -> None:
        """Publish to the main EventBus."""
        # Map dynamic events to ConfigurationEvent
        event_map = {
            DynamicEvent.SNAPSHOT_CREATED: ConfigurationEvent.LOADED,
            DynamicEvent.SNAPSHOT_ACTIVATED: ConfigurationEvent.RELOADED,
            DynamicEvent.SNAPSHOT_ROLLED_BACK: ConfigurationEvent.ROLLBACK,
            DynamicEvent.CONFIG_RELOADED: ConfigurationEvent.RELOADED,
            DynamicEvent.RELOAD_SUCCEEDED: ConfigurationEvent.UPDATED,
            DynamicEvent.RELOAD_FAILED: ConfigurationEvent.FAILED,
            DynamicEvent.VALIDATION_FAILED: ConfigurationEvent.VALIDATION_WARNING,
            DynamicEvent.CONFIG_CHANGED: ConfigurationEvent.UPDATED,
        }

        config_event = event_map.get(event_type)
        if config_event:
            self._event_bus.publish(
                config_event,
                affected_keys=event_data.get("affected_keys"),
                metadata=event_data,
            )

    def publish_snapshot_created(
        self,
        version: int,
        checksum: str,
        source: str = "dynamic",
    ) -> None:
        """Publish snapshot created event."""
        self.publish(
            DynamicEvent.SNAPSHOT_CREATED,
            data={"version": version, "checksum": checksum},
            source=source,
        )

    def publish_snapshot_activated(
        self,
        version: int,
        changed_keys: List[str],
        source: str = "dynamic",
    ) -> None:
        """Publish snapshot activated event."""
        self.publish(
            DynamicEvent.SNAPSHOT_ACTIVATED,
            data={"version": version},
            source=source,
            affected_keys=changed_keys,
        )

    def publish_rollback(
        self,
        from_version: int,
        to_version: int,
        source: str = "dynamic",
    ) -> None:
        """Publish rollback event."""
        self.publish(
            DynamicEvent.SNAPSHOT_ROLLED_BACK,
            data={"from": from_version, "to": to_version},
            source=source,
        )

    def publish_reload_success(
        self,
        version: int,
        duration: float,
        changed_keys: List[str],
    ) -> None:
        """Publish successful reload event."""
        self.publish(
            DynamicEvent.RELOAD_SUCCEEDED,
            data={"version": version, "duration": duration},
            affected_keys=changed_keys,
        )

    def publish_reload_failure(
        self,
        error: str,
        stage: str,
    ) -> None:
        """Publish failed reload event."""
        self.publish(
            DynamicEvent.RELOAD_FAILED,
            data={"error": error, "stage": stage},
        )

    def get_history(
        self,
        event_type: Optional[DynamicEvent] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get event history."""
        with self._lock:
            history = self._event_history
            if event_type:
                history = [
                    e for e in history
                    if e["event_type"] == event_type.value
                ]
            return history[-limit:]

    def get_stats(
        self,
    ) -> Dict[str, Any]:
        """Get publisher statistics."""
        with self._lock:
            listener_counts = {
                k: len(v) for k, v in self._listeners.items()
            }
            return {
                "total_listeners": sum(listener_counts.values()),
                "listener_counts": listener_counts,
                "history_size": len(self._event_history),
            }
