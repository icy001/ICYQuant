"""EventBus Adapter — connects the Scheduler to the platform EventBus.

The :class:`EventBusAdapter` enables event-driven scheduling:
* Publish scheduler lifecycle events (triggered, dispatched, completed, failed)
* Subscribe to platform events that may trigger schedules
* Event replay for recovery scenarios
* Event routing and filtering

Pipeline::

    Scheduler Events ──→ EventBus ──→ Subscribers
                                      ├── Workflow
                                      ├── OMS
                                      ├── Risk
                                      └── Execution
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventBusAdapterState(enum.Enum):
    """EventBus adapter connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISCONNECTING = "disconnecting"
    ERROR = "error"


class EventBusAdapter:
    """Adapter for publishing and subscribing to platform events.

    Responsibilities:
    * Publish scheduler events to the platform EventBus
    * Subscribe to platform events for trigger evaluation
    * Event replay for recovery and debugging
    * Event routing with topic-based filtering

    Usage::

        adapter = EventBusAdapter(event_bus=bus)
        await adapter.connect()
        await adapter.publish("scheduler.job.triggered", payload)
        await adapter.subscribe("market.open", on_market_open)
    """

    # Standard scheduler event topics
    TOPIC_JOB_TRIGGERED = "scheduler.job.triggered"
    TOPIC_JOB_DISPATCHED = "scheduler.job.dispatched"
    TOPIC_JOB_STARTED = "scheduler.job.started"
    TOPIC_JOB_COMPLETED = "scheduler.job.completed"
    TOPIC_JOB_FAILED = "scheduler.job.failed"
    TOPIC_JOB_RETRYING = "scheduler.job.retrying"
    TOPIC_SCHEDULE_CREATED = "scheduler.schedule.created"
    TOPIC_SCHEDULE_UPDATED = "scheduler.schedule.updated"
    TOPIC_SCHEDULE_DELETED = "scheduler.schedule.deleted"
    TOPIC_LEADER_ELECTED = "scheduler.cluster.leader_elected"
    TOPIC_FAILOVER = "scheduler.cluster.failover"
    TOPIC_NODE_JOINED = "scheduler.cluster.node_joined"
    TOPIC_NODE_LEFT = "scheduler.cluster.node_left"

    def __init__(self, event_bus: Any = None) -> None:
        self._bus = event_bus
        self._state = EventBusAdapterState.DISCONNECTED
        self._lock = threading.Lock()
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._publish_count: int = 0
        self._receive_count: int = 0
        self._event_log: List[Dict[str, Any]] = []
        self._max_event_log = 10000
        self._last_publish_at: Optional[datetime] = None
        self._last_receive_at: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> EventBusAdapterState:
        return self._state

    @property
    def publish_count(self) -> int:
        return self._publish_count

    @property
    def receive_count(self) -> int:
        return self._receive_count

    @property
    def subscriptions(self) -> List[str]:
        return list(self._subscriptions.keys())

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the platform EventBus."""
        self._set_state(EventBusAdapterState.CONNECTING)
        try:
            if self._bus and hasattr(self._bus, "connect"):
                await self._bus.connect()
            self._set_state(EventBusAdapterState.CONNECTED)
            logger.info("EventBusAdapter: connected")
        except Exception as exc:
            self._set_state(EventBusAdapterState.ERROR)
            logger.error("EventBusAdapter: connection failed: %s", exc)
            raise

    async def disconnect(self) -> None:
        """Disconnect from the EventBus."""
        self._set_state(EventBusAdapterState.DISCONNECTING)
        try:
            if self._bus and hasattr(self._bus, "disconnect"):
                await self._bus.disconnect()
            self._subscriptions.clear()
            self._set_state(EventBusAdapterState.DISCONNECTED)
        except Exception as exc:
            logger.warning("EventBusAdapter: disconnect error: %s", exc)

    async def synchronize(self) -> Dict[str, Any]:
        """Synchronize event bus state."""
        return {
            "state": self._state.value,
            "subscriptions": len(self._subscriptions),
            "publish_count": self._publish_count,
            "receive_count": self._receive_count,
        }

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish(self, topic: str, payload: Dict[str, Any], headers: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Publish a scheduler event to the platform EventBus.

        Args:
            topic: Event topic (e.g., 'scheduler.job.triggered')
            payload: Event payload data
            headers: Optional message headers (correlation_id, etc.)
        """
        self._publish_count += 1
        self._last_publish_at = datetime.now(timezone.utc)

        event = {
            "topic": topic,
            "payload": payload,
            "headers": headers or {},
            "timestamp": self._last_publish_at.isoformat(),
            "source": "scheduler",
        }

        # Log for replay
        self._log_event(event)

        result = {"topic": topic, "status": "published"}

        try:
            if self._bus and hasattr(self._bus, "publish"):
                await self._bus.publish(topic, payload, headers=headers)
        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)
            logger.error("EventBusAdapter: publish failed for %s: %s", topic, exc)

        return result

    # ------------------------------------------------------------------
    # Subscribe
    # ------------------------------------------------------------------

    async def subscribe(self, topic: str, handler: Callable) -> None:
        """Subscribe to a platform event topic.

        The handler will be called whenever an event is published to the topic.
        """
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []
            # Register with the actual event bus
            if self._bus and hasattr(self._bus, "subscribe"):
                await self._bus.subscribe(topic, self._on_event)

        self._subscriptions[topic].append(handler)
        logger.info("EventBusAdapter: subscribed to %s", topic)

    async def unsubscribe(self, topic: str, handler: Optional[Callable] = None) -> None:
        """Unsubscribe from a topic."""
        if topic not in self._subscriptions:
            return

        if handler:
            self._subscriptions[topic].remove(handler)
            if not self._subscriptions[topic]:
                del self._subscriptions[topic]
        else:
            del self._subscriptions[topic]

        logger.info("EventBusAdapter: unsubscribed from %s", topic)

    # ------------------------------------------------------------------
    # Event Replay
    # ------------------------------------------------------------------

    async def replay(self, topic: Optional[str] = None, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Replay events from the event log for recovery/debugging.

        Args:
            topic: Filter by topic (None = all topics)
            since: Only replay events after this time
        """
        events = self._event_log

        if topic:
            events = [e for e in events if e["topic"] == topic]
        if since:
            events = [e for e in events if e["timestamp"] >= since.isoformat()]

        logger.info("EventBusAdapter: replaying %d events", len(events))
        return events

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _on_event(self, topic: str, payload: Dict[str, Any], headers: Optional[Dict[str, Any]] = None) -> None:
        """Internal handler: called by the EventBus when a subscribed event arrives."""
        self._receive_count += 1
        self._last_receive_at = datetime.now(timezone.utc)

        handlers = self._subscriptions.get(topic, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(payload, headers)
                else:
                    handler(payload, headers)
            except Exception as exc:
                logger.warning("EventBusAdapter: handler error for %s: %s", topic, exc)

    def _log_event(self, event: Dict[str, Any]) -> None:
        """Append event to the replay log, trimming if needed."""
        self._event_log.append(event)
        if len(self._event_log) > self._max_event_log:
            self._event_log = self._event_log[-self._max_event_log:]

    def _set_state(self, state: EventBusAdapterState) -> None:
        with self._lock:
            self._state = state
