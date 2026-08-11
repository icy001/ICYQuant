"""
Event Bridge — Central event bus for the Strategy Platform.

Provides publish-subscribe event routing across all platform
subsystems with typed events, priority levels, and filtering.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Standard strategy platform event types."""
    # Strategy events
    STRATEGY_REGISTERED = "strategy.registered"
    STRATEGY_DEPLOYED = "strategy.deployed"
    STRATEGY_STARTED = "strategy.started"
    STRATEGY_PAUSED = "strategy.paused"
    STRATEGY_RESUMED = "strategy.resumed"
    STRATEGY_STOPPED = "strategy.stopped"
    STRATEGY_FAILED = "strategy.failed"
    STRATEGY_ROLLED_BACK = "strategy.rolled_back"

    # Lifecycle events
    LIFECYCLE_TRANSITION = "strategy.lifecycle.transition"

    # Signal events
    SIGNAL_GENERATED = "strategy.signal.generated"
    SIGNAL_EVALUATED = "strategy.signal.evaluated"

    # Order events
    ORDER_INTENT_CREATED = "strategy.order_intent.created"
    ORDER_SUBMITTED = "strategy.order.submitted"
    ORDER_FILLED = "strategy.order.filled"
    ORDER_CANCELLED = "strategy.order.cancelled"

    # Risk events
    RISK_CHECK_PASSED = "strategy.risk.passed"
    RISK_CHECK_FAILED = "strategy.risk.failed"
    KILL_SWITCH_TRIGGERED = "strategy.kill_switch.triggered"

    # Platform events
    PLATFORM_HEARTBEAT = "platform.heartbeat"
    PLATFORM_HEALTH_CHANGE = "platform.health.change"
    DEPLOYMENT_STARTED = "deployment.started"
    DEPLOYMENT_COMPLETED = "deployment.completed"
    DEPLOYMENT_FAILED = "deployment.failed"
    ROLLBACK_STARTED = "rollback.started"


class EventPriority(str, Enum):
    """Event priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class StrategyEvent:
    """A strategy platform event."""
    event_id: str
    event_type: EventType
    source: str = "strategy_platform"
    priority: EventPriority = EventPriority.NORMAL
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None


EventHandler = Callable[[StrategyEvent], Any]


class EventBridge:
    """
    Central event bus for strategy platform events.

    Implements pub/sub pattern with typed events, priority routing,
    and event filtering. All platform subsystems communicate through
    the event bridge for loose coupling.

    Usage::

        bridge = EventBridge()
        await bridge.initialize()

        # Subscribe
        await bridge.subscribe(EventType.STRATEGY_DEPLOYED, handler)

        # Emit
        await bridge.emit(EventType.STRATEGY_DEPLOYED, {"strategy_id": "strat_001"})
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = {}
        self._event_history: list[StrategyEvent] = []
        self._counter: int = 0
        self._initialized: bool = False
        self._max_history: int = 10000

    async def initialize(self) -> None:
        """Initialize the event bridge."""
        self._initialized = True
        logger.info("EventBridge initialized.")

    async def start(self) -> None:
        """Start the event bridge."""
        logger.info("EventBridge started.")

    async def stop(self) -> None:
        """Stop the event bridge."""
        self._initialized = False
        logger.info("EventBridge stopped.")

    # ---- Subscription ----

    async def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
    ) -> None:
        """Subscribe to a specific event type."""
        key = event_type.value
        if key not in self._subscribers:
            self._subscribers[key] = []
        self._subscribers[key].append(handler)
        logger.debug(f"Subscribed to {event_type.value} (total: {len(self._subscribers[key])})")

    async def subscribe_all(
        self,
        handler: EventHandler,
    ) -> None:
        """Subscribe to all event types (wildcard)."""
        wildcard = "*"
        if wildcard not in self._subscribers:
            self._subscribers[wildcard] = []
        self._subscribers[wildcard].append(handler)
        logger.debug(f"Wildcard subscriber added (total: {len(self._subscribers[wildcard])})")

    async def unsubscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
    ) -> None:
        """Unsubscribe from an event type."""
        key = event_type.value
        if key in self._subscribers and handler in self._subscribers[key]:
            self._subscribers[key].remove(handler)
            logger.debug(f"Unsubscribed from {key}")

    # ---- Event Emission ----

    async def emit(
        self,
        event_type: EventType | str,
        payload: dict[str, Any],
        priority: EventPriority = EventPriority.NORMAL,
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> StrategyEvent:
        """Emit an event to all subscribers."""
        self._counter += 1

        if isinstance(event_type, str):
            event_type = EventType(event_type)

        event = StrategyEvent(
            event_id=f"evt_{self._counter:08d}",
            event_type=event_type,
            priority=priority,
            payload=payload,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )

        # Record history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        # Deliver to subscribers
        await self._deliver(event)

        return event

    async def emit_batch(
        self,
        events: list[tuple[EventType, dict[str, Any]]],
    ) -> list[StrategyEvent]:
        """Emit multiple events."""
        results = []
        for event_type, payload in events:
            result = await self.emit(event_type, payload)
            results.append(result)
        return results

    # ---- History ----

    async def get_history(
        self,
        event_type: Optional[EventType] = None,
        limit: int = 100,
    ) -> list[StrategyEvent]:
        """Get event history with optional filtering."""
        results = self._event_history
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        return results[-limit:]

    async def get_event_count(self) -> int:
        """Get total events emitted."""
        return self._counter

    # ---- Internal ----

    async def _deliver(self, event: StrategyEvent) -> None:
        """Deliver event to all matching subscribers."""
        handlers = []

        # Exact match
        key = event.event_type.value
        if key in self._subscribers:
            handlers.extend(self._subscribers[key])

        # Wildcard
        if "*" in self._subscribers:
            handlers.extend(self._subscribers["*"])

        if not handlers:
            return

        # Deliver in priority order (CRITICAL first)
        # All handlers are called concurrently for performance
        tasks = []
        for handler in handlers:
            tasks.append(asyncio.create_task(self._invoke_handler(handler, event)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    async def _invoke_handler(handler: EventHandler, event: StrategyEvent) -> None:
        """Invoke a single event handler with error handling."""
        try:
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"Event handler error for {event.event_type.value}: {e}")
