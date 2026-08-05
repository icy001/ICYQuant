"""Service discovery event bus.

Provides ``ServiceEventType``, ``ServiceEvent``, and
``ServiceEventBus`` for publishing and subscribing to service
lifecycle events such as registration, deregistration, lease
renewal, and registry recovery.
"""

from __future__ import annotations

import inspect
import logging
import threading
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ServiceEventType(Enum):
    """Types of service discovery events."""

    SERVICE_REGISTERED = "service.registered"
    SERVICE_DEREGISTERED = "service.deregistered"
    SERVICE_UPDATED = "service.updated"
    LEASE_EXPIRED = "lease.expired"
    LEASE_RENEWED = "lease.renewed"
    NAMESPACE_CREATED = "namespace.created"
    NAMESPACE_DELETED = "namespace.deleted"
    REGISTRY_RECOVERED = "registry.recovered"
    REGISTRY_SYNCED = "registry.synced"
    HEARTBEAT_RECEIVED = "heartbeat.received"
    HEARTBEAT_LOST = "heartbeat.lost"
    LEASE_CREATED = "lease.created"
    SERVICE_HEALTHY = "service.healthy"
    SERVICE_UNHEALTHY = "service.unhealthy"
    SERVICE_RECOVERED = "service.recovered"
    SERVICE_QUARANTINED = "service.quarantined"


class ServiceEvent:
    """A service discovery event.

    Args:
        event_type: The type of event.
        service_name: Logical name of the affected service.
        instance_id: Identifier of the affected instance.
        namespace: Namespace the event applies to.
        timestamp: Event timestamp (defaults to now).
        data: Optional event payload.
    """

    __slots__ = (
        "event_type",
        "service_name",
        "instance_id",
        "namespace",
        "timestamp",
        "data",
    )

    def __init__(
        self,
        event_type: ServiceEventType,
        service_name: str = "",
        instance_id: str = "",
        namespace: str = "default",
        timestamp: Optional[datetime] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.event_type = event_type
        self.service_name = service_name
        self.instance_id = instance_id
        self.namespace = namespace
        self.timestamp = timestamp if timestamp is not None else datetime.utcnow()
        self.data = dict(data) if data else {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the event to a dictionary."""
        return {
            "event_type": self.event_type.value,
            "service_name": self.service_name,
            "instance_id": self.instance_id,
            "namespace": self.namespace,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "data": dict(self.data),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ServiceEvent:
        """Deserialize an event from a dictionary."""
        if data is None:
            data = {}
        event_type = data.get("event_type")
        if isinstance(event_type, str):
            try:
                event_type = ServiceEventType(event_type)
            except ValueError:
                event_type = ServiceEventType.SERVICE_UPDATED
        if not isinstance(event_type, ServiceEventType):
            event_type = ServiceEventType.SERVICE_UPDATED
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except ValueError:
                timestamp = None
        return cls(
            event_type=event_type,
            service_name=str(data.get("service_name", "")),
            instance_id=str(data.get("instance_id", "")),
            namespace=str(data.get("namespace", "default")),
            timestamp=timestamp if isinstance(timestamp, datetime) else None,
            data=dict(data.get("data", {}) or {}),
        )

    def __repr__(self) -> str:
        return (
            f"ServiceEvent(event_type={self.event_type.value!r}, "
            f"service_name={self.service_name!r}, instance_id={self.instance_id!r})"
        )


class ServiceEventBus:
    """Event bus for service discovery events.

    Supports multiple subscribers per event type. Thread-safe via a
    reentrant lock. Subscribers may be synchronous or asynchronous
    callables accepting a single ``ServiceEvent`` argument.
    """

    def __init__(self, max_history: int = 1000) -> None:
        self._lock = threading.RLock()
        self._subscribers: Dict[ServiceEventType, List[Callable]] = {}
        self._global_subscribers: List[Callable] = []
        self._history: List[ServiceEvent] = []
        self._stats: Dict[str, int] = {}
        self._max_history = max_history

    async def publish(self, event: ServiceEvent) -> None:
        """Publish an event to all matching subscribers.

        Records the event in history, updates statistics, and
        dispatches to subscribers via :meth:`notify`.
        """
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                excess = len(self._history) - self._max_history
                del self._history[:excess]
            key = event.event_type.value
            self._stats[key] = self._stats.get(key, 0) + 1
        await self.notify(event)

    async def notify(self, event: ServiceEvent) -> None:
        """Dispatch an event to registered subscribers."""
        with self._lock:
            handlers: List[Callable] = []
            handlers.extend(self._subscribers.get(event.event_type, []))
            handlers.extend(self._global_subscribers)
        for handler in list(handlers):
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception(
                    "Service event subscriber for %s failed.",
                    event.event_type.value,
                )

    def subscribe(
        self, event_type: ServiceEventType, callback: Callable
    ) -> None:
        """Subscribe a callback to a specific event type."""
        with self._lock:
            self._subscribers.setdefault(event_type, []).append(callback)
        logger.debug("Subscribed callback to %s.", event_type.value)

    def unsubscribe(
        self,
        event_type: ServiceEventType,
        callback: Optional[Callable] = None,
    ) -> None:
        """Unsubscribe a callback from an event type.

        If ``callback`` is None, all subscribers for the event type
        are removed.
        """
        with self._lock:
            if callback is None:
                self._subscribers.pop(event_type, None)
            else:
                handlers = self._subscribers.get(event_type, [])
                self._subscribers[event_type] = [
                    h for h in handlers if h != callback
                ]
                if not self._subscribers[event_type]:
                    self._subscribers.pop(event_type, None)
        logger.debug("Unsubscribed callback from %s.", event_type.value)

    def subscribe_all(self, callback: Callable) -> None:
        """Subscribe a callback to all event types."""
        with self._lock:
            self._global_subscribers.append(callback)
        logger.debug("Subscribed global callback to all event types.")

    def get_history(
        self, service_name: str = "", limit: int = 100
    ) -> List[ServiceEvent]:
        """Return recent events, optionally filtered by service name."""
        with self._lock:
            events = list(self._history)
        if service_name:
            events = [e for e in events if e.service_name == service_name]
        if limit is None or limit < 0:
            return events
        if limit == 0:
            return []
        return events[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the event bus."""
        with self._lock:
            subscriber_count = sum(
                len(v) for v in self._subscribers.values()
            ) + len(self._global_subscribers)
            return {
                "total_events": sum(self._stats.values()),
                "by_type": dict(self._stats),
                "subscriber_count": subscriber_count,
                "history_size": len(self._history),
                "max_history": self._max_history,
            }

    def clear(self) -> None:
        """Clear all subscribers and history."""
        with self._lock:
            self._subscribers.clear()
            self._global_subscribers.clear()
            self._history.clear()
            self._stats.clear()
