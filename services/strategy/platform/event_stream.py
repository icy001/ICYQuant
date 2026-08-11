"""
Event Stream — Real-time event streaming for the Strategy Platform.

Provides WebSocket-compatible event streaming with subscription
management, filtering, and backpressure handling.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class StreamSubscription:
    """An event stream subscription."""
    subscription_id: str
    event_types: list[str] = field(default_factory=list)
    strategy_ids: Optional[list[str]] = None
    filters: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True


@dataclass
class StreamMessage:
    """A message in the event stream."""
    message_id: str
    subscription_id: str
    event_type: str
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sequence_number: int = 0


class EventStream:
    """
    Real-time event streaming for strategy platform events.

    Manages client subscriptions, message routing, and provides
    a queue-based interface suitable for WebSocket delivery.

    Usage::

        stream = EventStream(event_bridge=bridge)
        await stream.initialize()
        sub = await stream.create_subscription(["strategy.*"], strategy_ids=["strat_001"])
        async for message in stream.consume(sub.subscription_id):
            print(message.payload)
    """

    def __init__(self, event_bridge: Any = None) -> None:
        self._event_bridge = event_bridge
        self._subscriptions: dict[str, StreamSubscription] = {}
        self._message_queues: dict[str, asyncio.Queue] = {}
        self._sequence: int = 0
        self._counter: int = 0
        self._initialized: bool = False
        self._dispatch_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Initialize the event stream."""
        self._initialized = True
        logger.info("EventStream initialized.")

    async def start(self) -> None:
        """Start the event stream dispatcher."""
        if self._event_bridge:
            await self._event_bridge.subscribe_all(self._on_event)
        logger.info("EventStream started.")

    async def stop(self) -> None:
        """Stop the event stream."""
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
        self._initialized = False
        logger.info("EventStream stopped.")

    # ---- Subscription Management ----

    async def create_subscription(
        self,
        event_types: list[str],
        strategy_ids: Optional[list[str]] = None,
        filters: Optional[dict[str, Any]] = None,
    ) -> StreamSubscription:
        """Create a new event stream subscription."""
        self._counter += 1
        subscription_id = f"sub_{self._counter:06d}"

        sub = StreamSubscription(
            subscription_id=subscription_id,
            event_types=event_types,
            strategy_ids=strategy_ids,
            filters=filters or {},
        )
        self._subscriptions[subscription_id] = sub
        self._message_queues[subscription_id] = asyncio.Queue(maxsize=1000)

        logger.info(f"Subscription created: {subscription_id} ({len(event_types)} event types)")
        return sub

    async def cancel_subscription(self, subscription_id: str) -> bool:
        """Cancel an event stream subscription."""
        sub = self._subscriptions.pop(subscription_id, None)
        if sub:
            sub.active = False
        self._message_queues.pop(subscription_id, None)
        logger.info(f"Subscription cancelled: {subscription_id}")
        return sub is not None

    async def get_subscription(self, subscription_id: str) -> Optional[StreamSubscription]:
        """Get a subscription by ID."""
        return self._subscriptions.get(subscription_id)

    # ---- Message Consumption ----

    async def consume(self, subscription_id: str) -> StreamMessage:
        """Consume the next message from a subscription queue (blocking)."""
        queue = self._message_queues.get(subscription_id)
        if not queue:
            raise ValueError(f"Subscription not found: {subscription_id}")
        return await queue.get()

    async def consume_nowait(self, subscription_id: str) -> Optional[StreamMessage]:
        """Consume a message without blocking."""
        queue = self._message_queues.get(subscription_id)
        if not queue:
            return None
        try:
            return queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def consume_batch(
        self,
        subscription_id: str,
        max_messages: int = 100,
        timeout: float = 1.0,
    ) -> list[StreamMessage]:
        """Consume a batch of messages."""
        queue = self._message_queues.get(subscription_id)
        if not queue:
            return []

        messages: list[StreamMessage] = []
        try:
            for _ in range(max_messages):
                message = await asyncio.wait_for(queue.get(), timeout=timeout / max_messages)
                messages.append(message)
        except asyncio.TimeoutError:
            pass

        return messages

    # ---- Publishing ----

    async def publish(
        self,
        event_type: str,
        payload: dict[str, Any],
        strategy_id: Optional[str] = None,
    ) -> list[str]:
        """Publish an event to matching subscriptions."""
        delivered_to: list[str] = []

        for sub_id, sub in self._subscriptions.items():
            if not sub.active:
                continue

            # Match event type
            if not self._match_event_type(event_type, sub.event_types):
                continue

            # Match strategy
            if sub.strategy_ids and strategy_id and strategy_id not in sub.strategy_ids:
                continue

            # Create message
            self._sequence += 1
            message = StreamMessage(
                message_id=f"msg_{self._sequence:08d}",
                subscription_id=sub_id,
                event_type=event_type,
                payload=payload,
                sequence_number=self._sequence,
            )

            # Deliver to queue
            queue = self._message_queues.get(sub_id)
            if queue:
                try:
                    queue.put_nowait(message)
                    delivered_to.append(sub_id)
                except asyncio.QueueFull:
                    logger.warning(f"Queue full for subscription: {sub_id}")

        return delivered_to

    # ---- Event Handler ----

    async def _on_event(self, event: Any) -> None:
        """Handle events from the event bridge."""
        strategy_id = event.payload.get("strategy_id") if hasattr(event, 'payload') else None
        event_type = event.event_type.value if hasattr(event, 'event_type') else str(event)
        await self.publish(event_type, event.payload if hasattr(event, 'payload') else {}, strategy_id)

    # ---- Internal ----

    @staticmethod
    def _match_event_type(event_type: str, patterns: list[str]) -> bool:
        """Match an event type against subscription patterns."""
        for pattern in patterns:
            if pattern == "*":
                return True
            if pattern.endswith(".*"):
                prefix = pattern[:-2]
                if event_type.startswith(prefix):
                    return True
            if pattern == event_type:
                return True
        return False

    async def health_check(self) -> dict[str, Any]:
        """Check event stream health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "active_subscriptions": len([s for s in self._subscriptions.values() if s.active]),
            "messages_sequenced": self._sequence,
            "queues": len(self._message_queues),
        }
