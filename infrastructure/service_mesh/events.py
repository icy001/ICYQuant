"""Event definitions and publishing for the Service Mesh.

Provides ``MeshEvent`` enum and ``MeshEventPublisher`` for
emitting structured events to the ICYQuant EventBus.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MeshEvent(str, Enum):
    """Events emitted by the service mesh."""

    MESH_STARTED = "mesh_started"
    MESH_STOPPED = "mesh_stopped"
    MESH_RELOADED = "mesh_reloaded"
    POLICY_UPDATED = "policy_updated"
    PROXY_RELOADED = "proxy_reloaded"
    SIDECAR_CREATED = "sidecar_created"
    SIDECAR_STARTED = "sidecar_started"
    SIDECAR_STOPPED = "sidecar_stopped"
    SIDECAR_ERROR = "sidecar_error"
    ROUTE_ADDED = "route_added"
    ROUTE_REMOVED = "route_removed"
    CONFIGURATION_PUBLISHED = "configuration_published"
    SYNC_COMPLETED = "sync_completed"


class MeshEventPublisher:
    """Publishes mesh events to registered handlers."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._handlers: Dict[str, List[Callable]] = {}
        self._all_handlers: List[Callable] = []
        self._history: List[Dict[str, Any]] = []
        self._max_history = 1000
        self._publish_count = 0

    def subscribe(
        self,
        handler: Callable,
        event_types: Optional[List[MeshEvent]] = None,
    ) -> None:
        """Register an event handler."""
        with self._lock:
            if event_types is None:
                self._all_handlers.append(handler)
            else:
                for et in event_types:
                    key = et.value
                    if key not in self._handlers:
                        self._handlers[key] = []
                    self._handlers[key].append(handler)

    async def publish(
        self,
        event_type: MeshEvent,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Publish a mesh event to all subscribed handlers."""
        with self._lock:
            self._publish_count += 1
            targets: List[Callable] = list(self._all_handlers)
            key = event_type.value
            if key in self._handlers:
                targets.extend(self._handlers[key])

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
                coro = handler(event_record)
                if asyncio.iscoroutine(coro):
                    await coro
                dispatched += 1
            except Exception as exc:
                errors.append(str(exc))
                logger.warning(
                    "Handler failed for %s: %s", event_type.value, exc
                )

        return {
            "success": True,
            "event_type": event_type.value,
            "dispatched": dispatched,
            "errors": errors,
            "id": self._publish_count,
        }

    def _add_to_history(self, record: Dict[str, Any]) -> None:
        with self._lock:
            self._history.append(record)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

    def get_history(
        self, limit: int = 50
    ) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._history[-limit:])

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "publish_count": self._publish_count,
                "handler_count": len(self._all_handlers)
                + sum(len(v) for v in self._handlers.values()),
                "specific_handlers": {
                    k: len(v) for k, v in self._handlers.items()
                },
                "history_size": len(self._history),
            }

    def clear(self) -> None:
        with self._lock:
            self._handlers.clear()
            self._all_handlers.clear()
            self._history.clear()
            self._publish_count = 0
