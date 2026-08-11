"""
Strategy domain events.

Event-driven communication model for strategy lifecycle and operational
events within the production strategy platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class StrategyEventType(str, Enum):
    """Types of strategy events."""

    # Lifecycle events
    STRATEGY_CREATED = "strategy.created"
    STRATEGY_VALIDATED = "strategy.validated"
    STRATEGY_REGISTERED = "strategy.registered"
    STRATEGY_DEPLOYED = "strategy.deployed"
    STRATEGY_STARTED = "strategy.started"
    STRATEGY_PAUSED = "strategy.paused"
    STRATEGY_RESUMED = "strategy.resumed"
    STRATEGY_STOPPED = "strategy.stopped"
    STRATEGY_FAILED = "strategy.failed"
    STRATEGY_ARCHIVED = "strategy.archived"
    STRATEGY_RECOVERED = "strategy.recovered"
    STRATEGY_DEGRADED = "strategy.degraded"

    # Operational events
    STRATEGY_EXECUTED = "strategy.executed"
    STRATEGY_SIGNAL_GENERATED = "strategy.signal_generated"
    STRATEGY_SNAPSHOT_CREATED = "strategy.snapshot_created"
    STRATEGY_VERSION_DEPLOYED = "strategy.version_deployed"
    STRATEGY_ROLLBACK = "strategy.rollback"

    # Administrative events
    STRATEGY_CONFIG_UPDATED = "strategy.config_updated"
    STRATEGY_PERMISSION_CHANGED = "strategy.permission_changed"
    STRATEGY_DEPENDENCY_UPDATED = "strategy.dependency_updated"


@dataclass
class StrategyEvent:
    """A domain event in the strategy platform."""

    event_id: str
    event_type: StrategyEventType
    strategy_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "strategy_engine"

    # Payload
    data: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "strategy_id": self.strategy_id,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "data": self.data,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "metadata": self.metadata,
        }


class StrategyEventPublisher:
    """Publishes strategy events to registered subscribers."""

    def __init__(self) -> None:
        from collections import defaultdict
        from typing import Callable, Coroutine

        self._subscribers: defaultdict[str, list] = defaultdict(list)
        self._initialized: bool = False

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("StrategyEventPublisher initialized")

    async def shutdown(self) -> None:
        self._subscribers.clear()
        self._initialized = False
        logger.info("StrategyEventPublisher shut down")

    def subscribe(
        self,
        event_type: StrategyEventType,
        handler,
    ) -> None:
        """Register a handler for a specific event type."""
        self._subscribers[event_type.value].append(handler)

    def unsubscribe(
        self,
        event_type: StrategyEventType,
        handler,
    ) -> None:
        """Remove a handler for a specific event type."""
        handlers = self._subscribers.get(event_type.value, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, event: StrategyEvent) -> None:
        """Publish an event to all subscribed handlers."""
        handlers = self._subscribers.get(event.event_type.value, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception(
                    "Error in event handler for %s", event.event_type.value
                )

    async def publish_many(self, events: list[StrategyEvent]) -> None:
        """Publish multiple events."""
        for event in events:
            await self.publish(event)


import logging

logger = logging.getLogger(__name__)
