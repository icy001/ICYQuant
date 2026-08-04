"""
Feature flag platform events.

Defines the event types used for feature flag
lifecycle changes, canary deployment, experiment
management, and snapshot synchronization.

All events follow the Event pattern and are
broadcast through the EventBus for subscribers.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class FeatureEventType(str, Enum):
    """All feature flag event types."""

    # Flag lifecycle
    FLAG_CREATED = "feature.flag.created"
    FLAG_UPDATED = "feature.flag.updated"
    FLAG_DELETED = "feature.flag.deleted"
    FLAG_ENABLED = "feature.flag.enabled"
    FLAG_DISABLED = "feature.flag.disabled"

    # Rule lifecycle
    RULE_CREATED = "feature.rule.created"
    RULE_UPDATED = "feature.rule.updated"
    RULE_DELETED = "feature.rule.deleted"

    # Rollout events
    ROLLOUT_STARTED = "feature.rollout.started"
    ROLLOUT_PROGRESSED = "feature.rollout.progressed"
    ROLLOUT_COMPLETED = "feature.rollout.completed"
    ROLLOUT_ROLLED_BACK = "feature.rollout.rolled_back"

    # Canary events
    CANARY_STARTED = "feature.canary.started"
    CANARY_PROMOTED = "feature.canary.promoted"
    CANARY_COMPLETED = "feature.canary.completed"
    CANARY_ROLLED_BACK = "feature.canary.rolled_back"
    CANARY_HEALTH_CHANGED = "feature.canary.health_changed"

    # Experiment events
    EXPERIMENT_STARTED = "feature.experiment.started"
    EXPERIMENT_PAUSED = "feature.experiment.paused"
    EXPERIMENT_RESUMED = "feature.experiment.resumed"
    EXPERIMENT_COMPLETED = "feature.experiment.completed"
    EXPERIMENT_ARCHIVED = "feature.experiment.archived"
    EXPERIMENT_WINNER_DECLARED = "feature.experiment.winner_declared"

    # Snapshot events
    SNAPSHOT_CREATED = "feature.snapshot.created"
    SNAPSHOT_ACTIVATED = "feature.snapshot.activated"
    SNAPSHOT_ROLLED_BACK = "feature.snapshot.rolled_back"

    # System events
    PLATFORM_STARTED = "feature.platform.started"
    PLATFORM_SHUTDOWN = "feature.platform.shutdown"
    HOT_RELOAD = "feature.hot_reload"


@dataclass
class FeatureEvent:
    """
    A feature flag platform event.

    All event types inherit from this base
    structure for consistent handling.

    Attributes:
        event_type: Type of the event.
        timestamp: When the event occurred.
        flag_key: Associated feature flag key.
        data: Event-specific payload.
        trace_id: Correlation trace ID.
        operator: Who triggered the event.
    """

    event_type: FeatureEventType = FeatureEventType.FLAG_UPDATED
    timestamp: datetime = field(default_factory=datetime.utcnow)
    flag_key: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    trace_id: str = ""
    operator: str = "system"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to dictionary."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "flag_key": self.flag_key,
            "data": self.data,
            "trace_id": self.trace_id,
            "operator": self.operator,
        }


class EventBus:
    """
    Async event bus for feature flag platform.

    Provides publish/subscribe pattern for
    feature flag lifecycle events, enabling
    decoupled communication between components.

    Features:
        - Async publish/consume
        - Wildcard subscription
        - Event filtering
        - Backpressure support
        - Memory-bounded event retention

    Usage:
        bus = EventBus()
        await bus.subscribe(FeatureEventType.FLAG_UPDATED, handler)
        await bus.publish(event)
    """

    def __init__(
        self,
        max_events: int = 10000,
    ) -> None:
        """
        Initialize event bus.

        Args:
            max_events: Maximum events to retain in history.
        """
        self._subscribers: Dict[str, List[Callable]] = {}
        self._wildcard_handlers: List[Callable] = []
        self._event_history: List[FeatureEvent] = []
        self._max_events = max_events
        self._lock = asyncio.Lock()
        self._event_count = 0

    async def subscribe(
        self,
        event_type: FeatureEventType,
        handler: Callable,
    ) -> None:
        """
        Subscribe to a specific event type.

        Args:
            event_type: Event type to listen for.
            handler: Async handler function.
        """
        key = event_type.value
        if key not in self._subscribers:
            self._subscribers[key] = []
        self._subscribers[key].append(handler)

    async def subscribe_all(
        self,
        handler: Callable,
    ) -> None:
        """
        Subscribe to all events (wildcard).

        Args:
            handler: Async handler function.
        """
        self._wildcard_handlers.append(handler)

    async def unsubscribe(
        self,
        event_type: FeatureEventType,
        handler: Callable,
    ) -> None:
        """
        Unsubscribe from a specific event type.

        Args:
            event_type: Event type to unsubscribe.
            handler: Handler function to remove.
        """
        key = event_type.value
        if key in self._subscribers:
            self._subscribers[key] = [
                h for h in self._subscribers[key] if h != handler
            ]

    async def publish(
        self,
        event: FeatureEvent,
    ) -> int:
        """
        Publish an event to all subscribers.

        Args:
            event: The event to publish.

        Returns:
            Number of subscribers notified.
        """
        key = event.event_type.value
        notified = 0

        # Store in history
        async with self._lock:
            self._event_history.append(event)
            self._event_count += 1
            if len(self._event_history) > self._max_events:
                self._event_history = self._event_history[-self._max_events:]

        # Notify type-specific subscribers
        handlers = list(self._subscribers.get(key, []))
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
                notified += 1
            except Exception as e:
                logger.error(
                    "Event handler error for %s: %s", key, e,
                )

        # Notify wildcard handlers
        for handler in self._wildcard_handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
                notified += 1
            except Exception as e:
                logger.error(
                    "Wildcard handler error for %s: %s", key, e,
                )

        return notified

    async def publish_batch(
        self,
        events: List[FeatureEvent],
    ) -> int:
        """
        Publish multiple events.

        Args:
            events: List of events to publish.

        Returns:
            Total number of subscribers notified.
        """
        total = 0
        for event in events:
            total += await self.publish(event)
        return total

    def get_event_history(
        self,
        event_type: Optional[FeatureEventType] = None,
        flag_key: Optional[str] = None,
        limit: int = 100,
    ) -> List[FeatureEvent]:
        """
        Get event history with optional filters.

        Args:
            event_type: Filter by event type.
            flag_key: Filter by flag key.
            limit: Max events to return.

        Returns:
            List of matching events.
        """
        results = list(reversed(self._event_history))

        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if flag_key:
            results = [e for e in results if e.flag_key == flag_key]

        return results[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        return {
            "total_events": self._event_count,
            "history_size": len(self._event_history),
            "type_subscribers": {
                k: len(v) for k, v in self._subscribers.items()
            },
            "wildcard_subscribers": len(self._wildcard_handlers),
            "max_events": self._max_events,
        }

    async def clear_history(self) -> None:
        """Clear event history."""
        async with self._lock:
            self._event_history.clear()

    async def shutdown(self) -> None:
        """Shutdown the event bus."""
        self._subscribers.clear()
        self._wildcard_handlers.clear()
        async with self._lock:
            self._event_history.clear()
