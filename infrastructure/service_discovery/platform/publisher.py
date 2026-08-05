"""Event publisher for ICYQuant service discovery platform.

Provides ``DiscoveryPublisher`` for publishing platform events
through the event bus, including service registration, updates,
heartbeats, recovery, failover, and topology changes.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .runtime_context import DiscoveryContext

logger = logging.getLogger(__name__)


class DiscoveryEvent(Enum):
    """Platform-level event types."""

    SERVICE_REGISTERED = "service.registered"
    SERVICE_DEREGISTERED = "service.deregistered"
    SERVICE_UPDATED = "service.updated"
    HEARTBEAT = "heartbeat"
    SERVICE_RECOVERED = "service.recovered"
    FAILOVER = "failover"
    TOPOLOGY_CHANGED = "topology.changed"
    SNAPSHOT_CREATED = "snapshot.created"
    CLUSTER_SYNCED = "cluster.synced"
    NODE_JOINED = "node.joined"
    NODE_LEFT = "node.left"
    PLATFORM_RELOADED = "platform.reloaded"


class DiscoveryPublisher:
    """Publishes platform events through the event bus.

    Bridges internal state changes to the event bus so that
    subscribers can react to service lifecycle events.
    """

    def __init__(
        self, context: Optional[DiscoveryContext] = None
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or DiscoveryContext()
        self._publish_count = 0
        self._event_counts: Dict[str, int] = {}
        self._history: List[Dict[str, Any]] = []
        self._max_history = 500
        self._last_publish: Optional[Dict[str, Any]] = None

    async def publish(
        self,
        event_type: DiscoveryEvent,
        service_name: str = "",
        instance_id: str = "",
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Publish a platform event.

        Args:
            event_type: The event type.
            service_name: Affected service name.
            instance_id: Affected instance ID.
            data: Optional event data.

        Returns:
            Publish result.
        """
        with self._lock:
            self._publish_count += 1
            key = event_type.value
            self._event_counts[key] = (
                self._event_counts.get(key, 0) + 1
            )

        event_bus = self._context.get("eventbus")
        published = False

        if event_bus is not None:
            publish_fn = getattr(event_bus, "publish", None)
            if callable(publish_fn):
                try:
                    event_obj = self._create_event(
                        event_type,
                        service_name,
                        instance_id,
                        data,
                    )
                    coro = publish_fn(event_obj)
                    if asyncio.iscoroutine(coro):
                        await coro
                    published = True
                except Exception as exc:
                    logger.warning(
                        "Event bus publish failed: %s", exc
                    )

        record: Dict[str, Any] = {
            "event_type": key,
            "service_name": service_name,
            "instance_id": instance_id,
            "published": published,
            "timestamp": datetime.utcnow().isoformat(),
            "data": dict(data) if data else {},
        }

        with self._lock:
            self._history.append(record)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            self._last_publish = record

        logger.debug(
            "Published event '%s' for service '%s'.",
            key,
            service_name,
        )
        return record

    async def publish_service_registered(
        self,
        service_name: str,
        instance_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return await self.publish(
            DiscoveryEvent.SERVICE_REGISTERED,
            service_name,
            instance_id,
            metadata or {},
        )

    async def publish_service_updated(
        self,
        service_name: str,
        instance_id: str = "",
        updates: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return await self.publish(
            DiscoveryEvent.SERVICE_UPDATED,
            service_name,
            instance_id,
            updates or {},
        )

    async def publish_service_recovered(
        self,
        service_name: str,
        instance_id: str = "",
    ) -> Dict[str, Any]:
        return await self.publish(
            DiscoveryEvent.SERVICE_RECOVERED,
            service_name,
            instance_id,
        )

    async def publish_failover(
        self,
        service_name: str,
        from_instance: str = "",
        to_instance: str = "",
    ) -> Dict[str, Any]:
        return await self.publish(
            DiscoveryEvent.FAILOVER,
            service_name,
            data={
                "from": from_instance,
                "to": to_instance,
            },
        )

    async def publish_topology_changed(
        self, topology_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return await self.publish(
            DiscoveryEvent.TOPOLOGY_CHANGED,
            data=topology_data or {},
        )

    def _create_event(
        self,
        event_type: DiscoveryEvent,
        service_name: str,
        instance_id: str,
        data: Optional[Dict[str, Any]],
    ) -> Any:
        """Create an event object for the event bus."""
        try:
            from .events import ServiceEvent, ServiceEventType

            mapping = {
                DiscoveryEvent.SERVICE_REGISTERED: (
                    ServiceEventType.SERVICE_REGISTERED
                ),
                DiscoveryEvent.SERVICE_DEREGISTERED: (
                    ServiceEventType.SERVICE_DEREGISTERED
                ),
                DiscoveryEvent.SERVICE_UPDATED: (
                    ServiceEventType.SERVICE_UPDATED
                ),
                DiscoveryEvent.HEARTBEAT: (
                    ServiceEventType.HEARTBEAT_RECEIVED
                ),
                DiscoveryEvent.SERVICE_RECOVERED: (
                    ServiceEventType.SERVICE_RECOVERED
                ),
            }

            bus_type = mapping.get(
                event_type, ServiceEventType.SERVICE_UPDATED
            )

            return ServiceEvent(
                event_type=bus_type,
                service_name=service_name,
                instance_id=instance_id,
                data=data,
            )
        except ImportError:
            return {
                "event_type": event_type.value,
                "service_name": service_name,
                "instance_id": instance_id,
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
            }

    def get_history(
        self, event_type: Optional[DiscoveryEvent] = None
    ) -> List[Dict[str, Any]]:
        with self._lock:
            if event_type is None:
                return list(self._history)
            return [
                h
                for h in self._history
                if h["event_type"] == event_type.value
            ]

    def get_event_counts(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._event_counts)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_publishes": self._publish_count,
                "by_type": dict(self._event_counts),
                "history_size": len(self._history),
                "last_publish": self._last_publish,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"DiscoveryPublisher(publishes={self._publish_count})"
            )
