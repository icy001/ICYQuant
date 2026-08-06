"""Platform EventBus Adapter for the Service Mesh Platform.

Provides ``PlatformEventBusAdapter`` for unified event publishing
and subscribing between the mesh platform and external systems.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .telemetry import PlatformTelemetry
from .metrics import PlatformMetrics

logger = logging.getLogger(__name__)


class PlatformEvent(str, Enum):
    """Events published by the mesh platform."""

    MESH_STARTED = "mesh_started"
    POLICY_UPDATED = "policy_updated"
    SIDECAR_INJECTED = "sidecar_injected"
    UPGRADE_COMPLETED = "upgrade_completed"
    SNAPSHOT_CREATED = "snapshot_created"
    MESH_STOPPED = "mesh_stopped"
    CONFIGURATION_CHANGED = "configuration_changed"
    DISCOVERY_CHANGED = "discovery_changed"
    CERTIFICATE_ROTATED = "certificate_rotated"
    FEATURE_FLAG_UPDATED = "feature_flag_updated"


class PlatformEventBusAdapter:
    """Unified event bus adapter for the mesh platform."""

    def __init__(
        self,
        telemetry: Optional[PlatformTelemetry] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._telemetry = telemetry or PlatformTelemetry()
        self._metrics = metrics or PlatformMetrics()
        self._publishers: Dict[str, List[Callable]] = {}
        self._subscribers: Dict[str, List[Callable]] = {}
        self._all_subscribers: List[Callable] = []
        self._event_history: List[Dict[str, Any]] = []
        self._max_history = 500
        self._publish_count = 0
        self._subscription_count = 0
        self._adapter_active = False

    async def initialize(self) -> Dict[str, Any]:
        self._adapter_active = True
        self._telemetry.log_platform_event(
            "eventbus_adapter_initialized", "eventbus",
        )
        logger.info("EventBus adapter initialized.")
        return {"success": True}

    async def shutdown(self) -> Dict[str, Any]:
        self._adapter_active = False
        self._telemetry.log_platform_event(
            "eventbus_adapter_shutdown", "eventbus",
        )
        logger.info("EventBus adapter shut down.")
        return {"success": True}

    @property
    def is_active(self) -> bool:
        return self._adapter_active

    def subscribe(
        self,
        handler: Callable,
        event_types: Optional[List[PlatformEvent]] = None,
    ) -> None:
        """Subscribe to mesh platform events."""
        self._subscription_count += 1
        if event_types is None:
            self._all_subscribers.append(handler)
        else:
            for et in event_types:
                key = et.value
                if key not in self._subscribers:
                    self._subscribers[key] = []
                self._subscribers[key].append(handler)

    def register_publisher(
        self,
        event_type: PlatformEvent,
        publisher: Callable,
    ) -> None:
        """Register an event publisher."""
        key = event_type.value
        if key not in self._publishers:
            self._publishers[key] = []
        self._publishers[key].append(publisher)

    async def publish(
        self,
        event_type: PlatformEvent,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Publish a mesh platform event."""
        self._publish_count += 1

        with self._lock:
            targets: List[Callable] = list(self._all_subscribers)
            key = event_type.value
            if key in self._subscribers:
                targets.extend(self._subscribers[key])

        event_record: Dict[str, Any] = {
            "event_type": event_type.value,
            "data": data or {},
            "timestamp": datetime.utcnow().isoformat(),
            "id": self._publish_count,
        }

        self._add_to_history(event_record)

        dispatched = 0
        errors: List[str] = []

        for handler in targets:
            try:
                result = handler(event_record)
                if asyncio.iscoroutine(result):
                    result = await result
                dispatched += 1
            except Exception as exc:
                errors.append(str(exc))
                logger.warning(
                    "Event handler failed for %s: %s",
                    event_type.value,
                    exc,
                )

        self._metrics.increment_counter(
            "icyquant_mesh_events_published_total",
            labels={"event_type": event_type.value},
        )
        self._telemetry.log_platform_event(
            event_type.value, "eventbus",
            {"dispatched": dispatched,
             "errors": len(errors)},
        )

        return {
            "success": True,
            "event_type": event_type.value,
            "dispatched": dispatched,
            "errors": errors,
            "id": self._publish_count,
        }

    async def publish_mesh_started(
        self, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return await self.publish(
            PlatformEvent.MESH_STARTED, data
        )

    async def publish_policy_updated(
        self, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return await self.publish(
            PlatformEvent.POLICY_UPDATED, data
        )

    async def publish_sidecar_injected(
        self, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return await self.publish(
            PlatformEvent.SIDECAR_INJECTED, data
        )

    async def publish_upgrade_completed(
        self, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return await self.publish(
            PlatformEvent.UPGRADE_COMPLETED, data
        )

    async def publish_snapshot_created(
        self, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return await self.publish(
            PlatformEvent.SNAPSHOT_CREATED, data
        )

    async def publish_configuration_changed(
        self, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return await self.publish(
            PlatformEvent.CONFIGURATION_CHANGED, data
        )

    async def publish_discovery_changed(
        self, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return await self.publish(
            PlatformEvent.DISCOVERY_CHANGED, data
        )

    async def publish_certificate_rotated(
        self, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return await self.publish(
            PlatformEvent.CERTIFICATE_ROTATED, data
        )

    async def publish_feature_flag_updated(
        self, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return await self.publish(
            PlatformEvent.FEATURE_FLAG_UPDATED, data
        )

    def _add_to_history(self, record: Dict[str, Any]) -> None:
        with self._lock:
            self._event_history.append(record)
            if len(self._event_history) > self._max_history:
                self._event_history = (
                    self._event_history[-self._max_history:]
                )

    def get_history(
        self, limit: int = 50
    ) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._event_history[-limit:])

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "active": self._adapter_active,
                "publish_count": self._publish_count,
                "subscription_count": self._subscription_count,
                "subscriber_count": len(self._all_subscribers)
                + sum(
                    len(v) for v in self._subscribers.values()
                ),
                "publisher_count": sum(
                    len(v) for v in self._publishers.values()
                ),
                "history_size": len(self._event_history),
            }

    def clear(self) -> None:
        with self._lock:
            self._publishers.clear()
            self._subscribers.clear()
            self._all_subscribers.clear()
            self._event_history.clear()
            self._publish_count = 0

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"PlatformEventBusAdapter("
                f"published={self._publish_count}, "
                f"active={self._adapter_active})"
            )
