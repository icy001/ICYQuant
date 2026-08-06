"""Runtime Events — event bus for workflow execution events.

Publishes lifecycle events throughout the workflow execution pipeline:
* WorkflowStarted / WorkflowCompleted / WorkflowFailed
* NodeStarted / NodeCompleted / NodeFailed
* CheckpointCreated / SnapshotTaken

All events are published to the ICYQuant EventBus for consumption by
monitoring, alerting, and downstream systems.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class RuntimeEventBus:
    """Publishes workflow execution events to registered subscribers.

    Events flow::

        WorkflowStarted → NodeStarted* → NodeCompleted* → WorkflowCompleted
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable]] = {}
        self._running = False
        self._event_history: List[Dict[str, Any]] = []
        self._max_history = 1000

    def start(self) -> None:
        self._running = True
        logger.info("RuntimeEventBus: started")

    def shutdown(self) -> None:
        self._running = False
        self._subscribers.clear()
        logger.info("RuntimeEventBus: shutdown")

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish an event to all subscribers of the given type."""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        # Notify subscribers
        subscribers = self._subscribers.get(event_type, [])
        for callback in subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as exc:
                logger.error("EventBus: subscriber error for %s: %s", event_type, exc)

    # ------------------------------------------------------------------
    # Subscribe
    # ------------------------------------------------------------------

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """Subscribe to events of a specific type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Remove a subscription."""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [c for c in self._subscribers[event_type] if c is not callback]

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_history(self, event_type: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent events, optionally filtered by type."""
        if event_type:
            filtered = [e for e in self._event_history if e["type"] == event_type]
            return filtered[-limit:]
        return self._event_history[-limit:]

    def clear_history(self) -> None:
        self._event_history.clear()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "subscriber_count": sum(len(v) for v in self._subscribers.values()),
            "event_types": list(self._subscribers.keys()),
            "history_size": len(self._event_history),
        }
