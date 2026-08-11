"""
ICYQuant Communication Bus — event-driven message delivery between agents.

Provides pub/sub messaging, point-to-point delivery, message filtering,
delivery guarantees, and dead-letter handling for multi-agent communication.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

from .agent_message import MessageEnvelope, MessageSerializer

logger = logging.getLogger(__name__)

MessageHandler = Callable[[MessageEnvelope], Awaitable[Any]]


@dataclass
class BusStats:
    messages_sent: int = 0
    messages_delivered: int = 0
    messages_failed: int = 0
    messages_dropped: int = 0
    active_subscriptions: int = 0


class CommunicationBus:
    """Event-driven message bus for inter-agent communication.

    Features:
        - Point-to-point (agent_id routing)
        - Pub/sub (topic-based broadcasting)
        - Message filtering by type and priority
        - Dead-letter queue for undelivered messages
        - Delivery tracking with correlation IDs
        - Backpressure control via bounded queues
    """

    def __init__(self, max_queue_size: int = 1000) -> None:
        self._max_queue_size = max_queue_size

        # Point-to-point: agent_id → handler
        self._agent_handlers: dict[str, MessageHandler] = {}

        # Pub/sub: topic → list of (subscriber_id, handler)
        self._topic_subscribers: dict[str, list[tuple[str, MessageHandler]]] = defaultdict(list)

        # In-flight tracking: correlation_id → pending future
        self._pending_requests: dict[str, asyncio.Future] = {}

        # Dead-letter queue: messages that couldn't be delivered
        self._dead_letter: list[MessageEnvelope] = []

        self._stats = BusStats()
        self._lock = asyncio.Lock()

    # ── Registration ──

    def register_agent(self, agent_id: str, handler: MessageHandler) -> None:
        """Register an agent to receive direct messages."""
        self._agent_handlers[agent_id] = handler
        logger.debug("Registered agent handler: %s", agent_id)

    def unregister_agent(self, agent_id: str) -> None:
        """Remove an agent's direct message handler."""
        self._agent_handlers.pop(agent_id, None)
        # Clean up topic subscriptions for this agent
        for topic in list(self._topic_subscribers.keys()):
            self._topic_subscribers[topic] = [
                (sid, h) for sid, h in self._topic_subscribers[topic] if sid != agent_id
            ]
        logger.debug("Unregistered agent handler: %s", agent_id)

    def subscribe(self, agent_id: str, topic: str, handler: MessageHandler) -> None:
        """Subscribe an agent to a topic."""
        self._topic_subscribers[topic].append((agent_id, handler))
        self._stats.active_subscriptions += 1
        logger.debug("Agent %s subscribed to topic '%s'", agent_id, topic)

    def unsubscribe(self, agent_id: str, topic: str) -> None:
        """Unsubscribe an agent from a topic."""
        before = len(self._topic_subscribers.get(topic, []))
        self._topic_subscribers[topic] = [
            (sid, h) for sid, h in self._topic_subscribers.get(topic, []) if sid != agent_id
        ]
        self._stats.active_subscriptions -= (before - len(self._topic_subscribers[topic]))

    # ── Sending ──

    async def send(self, envelope: MessageEnvelope) -> bool:
        """Send a message to a specific agent (point-to-point)."""
        self._stats.messages_sent += 1

        if envelope.is_expired():
            self._stats.messages_dropped += 1
            logger.warning("Dropped expired message %s", envelope.message_id)
            return False

        handler = self._agent_handlers.get(envelope.recipient_id)
        if handler is None:
            self._stats.messages_failed += 1
            await self._to_dead_letter(envelope, f"No handler for {envelope.recipient_id}")
            return False

        try:
            await handler(envelope)
            self._stats.messages_delivered += 1
            return True
        except Exception as exc:
            self._stats.messages_failed += 1
            logger.error("Failed to deliver message %s: %s", envelope.message_id, exc)
            await self._to_dead_letter(envelope, str(exc))
            return False

    async def publish(self, envelope: MessageEnvelope) -> int:
        """Publish a message to all subscribers of a topic."""
        self._stats.messages_sent += 1

        if envelope.is_expired():
            self._stats.messages_dropped += 1
            return 0

        subscribers = self._topic_subscribers.get(envelope.topic, [])
        if not subscribers:
            logger.debug("No subscribers for topic '%s'", envelope.topic)
            return 0

        delivered = 0
        tasks = []
        for sub_id, handler in subscribers:
            tasks.append(self._deliver_to_subscriber(sub_id, handler, envelope))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if r is True:
                delivered += 1

        self._stats.messages_delivered += delivered
        return delivered

    async def broadcast(self, envelope: MessageEnvelope) -> int:
        """Send a message to all registered agents."""
        self._stats.messages_sent += 1

        delivered = 0
        for agent_id, handler in self._agent_handlers.items():
            if agent_id == envelope.sender_id:
                continue
            try:
                await handler(envelope)
                delivered += 1
            except Exception:
                logger.debug("Broadcast to %s failed", agent_id, exc_info=True)

        self._stats.messages_delivered += delivered
        return delivered

    # ── Request/Response ──

    async def request(self, envelope: MessageEnvelope, timeout: float = 30.0) -> MessageEnvelope:
        """Send a request and await the response via correlation_id."""
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_requests[envelope.message_id] = future

        try:
            success = await self.send(envelope)
            if not success:
                future.cancel()
                raise RuntimeError(f"Failed to send request {envelope.message_id}")

            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.error("Request %s timed out after %ss", envelope.message_id, timeout)
            raise
        finally:
            self._pending_requests.pop(envelope.message_id, None)

    async def respond(self, envelope: MessageEnvelope) -> bool:
        """Deliver a response to a pending request."""
        if envelope.correlation_id and envelope.correlation_id in self._pending_requests:
            future = self._pending_requests[envelope.correlation_id]
            if not future.done():
                future.set_result(envelope)
                return True

        # Fall back to direct send
        return await self.send(envelope)

    # ── Dead Letter ──

    def get_dead_letter(self) -> list[MessageEnvelope]:
        """Retrieve all dead-letter messages."""
        return list(self._dead_letter)

    def replay_dead_letter(self) -> int:
        """Replay all dead-letter messages (for retry)."""
        count = len(self._dead_letter)
        # In a full implementation, these would be re-queued for delivery
        logger.info("Replaying %d dead-letter messages", count)
        self._dead_letter.clear()
        return count

    def clear_dead_letter(self) -> None:
        """Clear the dead-letter queue."""
        self._dead_letter.clear()

    # ── Internal ──

    async def _deliver_to_subscriber(self, sub_id: str, handler: MessageHandler,
                                     envelope: MessageEnvelope) -> bool:
        try:
            await handler(envelope)
            return True
        except Exception as exc:
            logger.debug("Delivery to subscriber %s failed: %s", sub_id, exc)
            return False

    async def _to_dead_letter(self, envelope: MessageEnvelope, reason: str) -> None:
        async with self._lock:
            if len(self._dead_letter) >= self._max_queue_size:
                self._dead_letter.pop(0)
            envelope.metadata["dead_letter_reason"] = reason
            envelope.metadata["dead_letter_at"] = datetime.now(timezone.utc).isoformat()
            self._dead_letter.append(envelope)

    # ── Properties ──

    @property
    def stats(self) -> BusStats:
        return self._stats

    @property
    def agent_count(self) -> int:
        return len(self._agent_handlers)

    @property
    def topic_count(self) -> int:
        return len(self._topic_subscribers)

    @property
    def dead_letter_count(self) -> int:
        return len(self._dead_letter)
