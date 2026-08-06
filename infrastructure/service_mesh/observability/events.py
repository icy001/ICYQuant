"""Observability events for ICYQuant Service Mesh.

Provides ``ObservabilityEvent`` enum and ``ObservabilityEventPublisher``
for emitting structured observability events across the mesh.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ObservabilityEvent(str, Enum):
    """Events emitted by the observability platform."""

    TRACE_STARTED = "trace_started"
    TRACE_COMPLETED = "trace_completed"
    SPAN_CREATED = "span_created"
    SPAN_COMPLETED = "span_completed"
    METRICS_FLUSHED = "metrics_flushed"
    ACCESS_LOGGED = "access_logged"
    POLICY_EVALUATED = "policy_evaluated"
    POLICY_CHANGED = "policy_changed"
    SLO_VIOLATION = "slo_violation"
    SLI_UPDATED = "sli_updated"
    ANOMALY_DETECTED = "anomaly_detected"
    RUNTIME_ANALYZED = "runtime_analyzed"
    DASHBOARD_REQUESTED = "dashboard_requested"
    ADAPTIVE_ADJUSTMENT = "adaptive_adjustment"


class ObservabilityEventPublisher:
    """Publishes observability events to registered handlers."""

    def __init__(self, max_history: int = 2000) -> None:
        self._lock = threading.RLock()
        self._handlers: Dict[str, List[Callable]] = {}
        self._all_handlers: List[Callable] = []
        self._history: List[Dict[str, Any]] = []
        self._max_history = max_history
        self._publish_count = 0

    def subscribe(
        self,
        handler: Callable,
        event_types: Optional[List[ObservabilityEvent]] = None,
    ) -> None:
        with self._lock:
            if event_types is None:
                self._all_handlers.append(handler)
            else:
                for et in event_types:
                    key = et.value
                    if key not in self._handlers:
                        self._handlers[key] = []
                    self._handlers[key].append(handler)

    def unsubscribe(self, handler: Callable) -> bool:
        with self._lock:
            removed = False
            if handler in self._all_handlers:
                self._all_handlers.remove(handler)
                removed = True
            for handlers in self._handlers.values():
                if handler in handlers:
                    handlers.remove(handler)
                    removed = True
            return removed

    def publish(
        self,
        event_type: ObservabilityEvent,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        event = {
            "event_type": event_type.value,
            "data": data or {},
            "timestamp": datetime.utcnow().isoformat(),
            "seq": self._next_seq(),
        }
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            handlers = list(self._all_handlers)
            key = event_type.value
            if key in self._handlers:
                handlers.extend(self._handlers[key])
            self._publish_count += 1

        for handler in handlers:
            try:
                result = handler(event)
                if asyncio_iscoro(result):
                    asyncio_ensure(result)
            except Exception as exc:
                logger.warning(
                    "Observability event handler failed: %s", exc
                )
        return event

    def _next_seq(self) -> int:
        with self._lock:
            return self._publish_count + 1

    def get_history(
        self,
        event_type: Optional[ObservabilityEvent] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            events = list(self._history)
        if event_type:
            events = [e for e in events if e["event_type"] == event_type.value]
        return events[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "publish_count": self._publish_count,
                "stored_events": len(self._history),
                "handler_count": len(self._all_handlers)
                + sum(len(h) for h in self._handlers.values()),
            }

    def clear(self) -> None:
        with self._lock:
            self._history.clear()


def asyncio_iscoro(obj: Any) -> bool:
    import asyncio

    return asyncio.iscoroutine(obj)


def asyncio_ensure(coro: Any) -> None:
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(coro)
        else:
            loop.run_until_complete(coro)
    except RuntimeError:
        pass
