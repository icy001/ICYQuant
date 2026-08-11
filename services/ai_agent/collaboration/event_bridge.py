"""Event Bridge — event-driven bridge between internal agent events and external systems.

Pipeline:
    Agent Event (status change, task complete, health change)
        -> EventBridge.publish() (create BridgeEvent)
        -> EventBridge.route() (route to handlers by event type)
        -> external subscribers / internal MessageQueue
        -> EventBridge.subscribe() / unsubscribe() (manage subscriptions)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from services.ai_agent.collaboration.message_queue import MessageQueue, QueueItem, QueuePriority

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of events in the agent collaboration system."""
    AGENT_REGISTERED = "agent.registered"
    AGENT_UNREGISTERED = "agent.unregistered"
    AGENT_STATUS_CHANGED = "agent.status_changed"
    AGENT_HEARTBEAT = "agent.heartbeat"
    AGENT_HEALTH_DEGRADED = "agent.health_degraded"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    CONSENSUS_REACHED = "consensus.reached"
    CONSENSUS_FAILED = "consensus.failed"
    CONFLICT_DETECTED = "conflict.detected"
    CONFLICT_RESOLVED = "conflict.resolved"
    MEMORY_UPDATED = "memory.updated"
    BLACKBOARD_UPDATED = "blackboard.updated"
    COORDINATION_STARTED = "coordination.started"
    COORDINATION_COMPLETED = "coordination.completed"


@dataclass
class BridgeEvent:
    """An event bridged between agent system and external consumers.

    Attributes:
        event_id: Unique event identifier.
        event_type: Type of the event.
        source_agent_id: Agent that generated the event.
        payload: Event payload data.
        timestamp: When the event occurred.
        correlation_id: Optional correlation ID for tracing.
        metadata: Additional metadata.
    """

    event_id: str = field(default_factory=lambda: uuid4().hex)
    event_type: EventType = EventType.AGENT_STATUS_CHANGED
    source_agent_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return event as a dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source_agent_id": self.source_agent_id,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
        }


EventHandler = Callable[[BridgeEvent], Any]


class EventBridge:
    """Event-driven bridge connecting agent events to internal and external systems.

    Publishes agent lifecycle and operational events to subscribers. Routes
    events by type and can forward to external monitoring systems.

    Supports:
        - Event publishing by type
        - Subscription management (subscribe/unsubscribe)
        - Event routing to internal MessageQueue
        - Correlation ID for distributed tracing
        - Event history (configurable retention)

    Usage:
        bridge = EventBridge(message_queue)
        await bridge.initialize()
        bridge.subscribe(EventType.TASK_COMPLETED, my_handler)
        await bridge.publish(BridgeEvent(event_type=EventType.TASK_COMPLETED, ...))
    """

    def __init__(self, message_queue: MessageQueue) -> None:
        """Initialize the event bridge.

        Args:
            message_queue: Message queue for internal event delivery.
        """
        self._message_queue: MessageQueue = message_queue
        self._subscribers: Dict[EventType, List[EventHandler]] = {
            et: [] for et in EventType
        }
        self._wildcard_subscribers: List[EventHandler] = []
        self._event_history: List[BridgeEvent] = []
        self._max_history: int = 1000
        self._initialized: bool = False
        logger.info("EventBridge created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the event bridge."""
        if self._initialized:
            logger.warning("EventBridge already initialized")
            return
        self._initialized = True
        logger.info("EventBridge initialized")

    async def shutdown(self) -> None:
        """Shut down the event bridge."""
        if not self._initialized:
            return
        for et in self._subscribers:
            self._subscribers[et].clear()
        self._wildcard_subscribers.clear()
        self._event_history.clear()
        self._initialized = False
        logger.info("EventBridge shutdown complete")

    # ── Publish ──

    async def publish(self, event: BridgeEvent) -> None:
        """Publish an event to all subscribers.

        Args:
            event: The event to publish.
        """
        if not self._initialized:
            raise RuntimeError("EventBridge not initialized")

        # Record in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        # Notify type-specific subscribers
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("Event handler failed for %s", event.event_type.value)

        # Notify wildcard subscribers
        for handler in self._wildcard_subscribers:
            try:
                handler(event)
            except Exception:
                logger.exception("Wildcard event handler failed")

        # Forward to message queue
        await self._forward_to_queue(event)

        logger.debug("Event published: %s (source=%s)",
                     event.event_type.value, event.source_agent_id)

    async def publish_batch(self, events: List[BridgeEvent]) -> None:
        """Publish multiple events.

        Args:
            events: List of events to publish.
        """
        for event in events:
            await self.publish(event)

    # ── Subscribe ──

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe to a specific event type.

        Args:
            event_type: The event type to subscribe to.
            handler: Callback for handling the event.
        """
        self._subscribers[event_type].append(handler)
        logger.debug("Subscribed to %s", event_type.value)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe to all event types (wildcard).

        Args:
            handler: Callback for handling events.
        """
        self._wildcard_subscribers.append(handler)
        logger.debug("Wildcard subscription added")

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unsubscribe from an event type.

        Args:
            event_type: The event type.
            handler: The handler to remove.
        """
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)
            logger.debug("Unsubscribed from %s", event_type.value)

    # ── Forwarding ──

    async def _forward_to_queue(self, event: BridgeEvent) -> None:
        """Forward an event to the internal message queue.

        Args:
            event: The event to forward.
        """
        item = QueueItem(
            topic=f"event.{event.event_type.value}",
            payload=event.to_dict(),
            priority=QueuePriority.NORMAL,
            sender_id=event.source_agent_id,
        )
        await self._message_queue.enqueue(item)

    # ── Query ──

    def get_history(
        self,
        event_type: Optional[EventType] = None,
        limit: int = 50,
    ) -> List[BridgeEvent]:
        """Retrieve event history with optional filtering.

        Args:
            event_type: Filter by event type. None for all types.
            limit: Maximum events to return.

        Returns:
            List of matching events (most recent first).
        """
        events = self._event_history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return list(reversed(events))[:limit]

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the event bridge state.

        Returns:
            Dict with subscriber counts and history size.
        """
        total_subscribers = sum(len(h) for h in self._subscribers.values())
        total_subscribers += len(self._wildcard_subscribers)
        return {
            "initialized": self._initialized,
            "total_subscribers": total_subscribers,
            "type_subscriptions": {
                et.value: len(handlers)
                for et, handlers in self._subscribers.items()
                if handlers
            },
            "history_size": len(self._event_history),
            "max_history": self._max_history,
        }
