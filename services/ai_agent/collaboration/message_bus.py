"""Message Bus — unified inter-agent communication bus with pub/sub, RPC, broadcast, and stream.

Pipeline:
    Agent (publisher)
        -> MessageBus.publish() (topic + payload)
        -> MessageRouter.route() (determine targets)
        -> MessageQueue.enqueue() (persist for delivery)
        -> EventBridge.publish() (emit event)
        -> Agent (subscriber) receives message

    Agent (subscriber)
        -> MessageBus.subscribe() (register interest in topics)
        -> MessageBus.poll() / MessageBus.request() (receive messages)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from services.ai_agent.collaboration.message_queue import (
    MessageQueue,
    QueueItem,
    QueuePriority,
)
from services.ai_agent.collaboration.message_router import (
    MessageRouter,
    RoutingAction,
)
from services.ai_agent.collaboration.event_bridge import (
    EventBridge,
    EventType,
)

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """Types of inter-agent messages."""
    PUBLISH = "publish"
    REQUEST = "request"
    RESPONSE = "response"
    BROADCAST = "broadcast"
    STREAM = "stream"


@dataclass
class Message:
    """A message exchanged between agents.

    Attributes:
        message_id: Unique message identifier.
        msg_type: Message type.
        topic: Message topic for routing.
        sender_id: ID of the sending agent.
        payload: Message payload.
        correlation_id: For request-response correlation.
        timestamp: When the message was created.
        ttl_seconds: Time-to-live in seconds.
    """

    message_id: str = field(default_factory=lambda: uuid4().hex)
    msg_type: MessageType = MessageType.PUBLISH
    topic: str = ""
    sender_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: float = 30.0

    def to_dict(self) -> Dict[str, Any]:
        """Return message as a dictionary."""
        return {
            "message_id": self.message_id,
            "msg_type": self.msg_type.value,
            "topic": self.topic,
            "sender_id": self.sender_id,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MessageEnvelope:
    """A message wrapped with routing metadata for delivery.

    Attributes:
        message: The original message.
        targets: List of target agent IDs.
        routing_action: The routing action applied.
        delivered_at: When the envelope was delivered.
    """

    message: Message = field(default_factory=Message)
    targets: List[str] = field(default_factory=list)
    routing_action: RoutingAction = RoutingAction.DELIVER
    delivered_at: Optional[datetime] = None


@dataclass
class Subscription:
    """A subscription to message topics.

    Attributes:
        subscription_id: Unique subscription identifier.
        agent_id: Subscribing agent ID.
        topic_pattern: Regex pattern for topic matching.
        handler: Optional async callback for received messages.
        queue: Local queue for polled messages.
    """

    subscription_id: str = field(default_factory=lambda: uuid4().hex)
    agent_id: str = ""
    topic_pattern: str = ".*"
    handler: Optional[Callable[..., Any]] = None
    queue: List[Message] = field(default_factory=list)

    def matches_topic(self, topic: str) -> bool:
        """Check whether this subscription matches a topic.

        Args:
            topic: The topic to check.

        Returns:
            True if the topic matches the pattern.
        """
        import re
        try:
            return bool(re.match(self.topic_pattern, topic))
        except re.error:
            return False


class MessageBus:
    """Unified inter-agent communication bus.

    The central nervous system of the multi-agent framework. Provides
    publish/subscribe, request/response, broadcast, and streaming
    communication patterns between agents.

    Supports:
        - Publish/Subscribe (topic-based)
        - Request/Response (synchronous RPC-style)
        - Broadcast (to all agents)
        - Stream (continuous data flow)
        - Message routing via MessageRouter
        - Persistent delivery via MessageQueue
        - Event emission via EventBridge

    Usage:
        bus = MessageBus(queue, router, bridge)
        await bus.initialize()
        bus.subscribe("research_agent", r"market\..*")
        await bus.publish(Message(topic="market.update", payload={...}))
        msgs = await bus.poll("research_agent")
    """

    def __init__(
        self,
        message_queue: MessageQueue,
        message_router: MessageRouter,
        event_bridge: EventBridge,
    ) -> None:
        """Initialize the message bus.

        Args:
            message_queue: Queue for persistent message delivery.
            message_router: Router for topic-based message routing.
            event_bridge: Bridge for event emission.
        """
        self._queue: MessageQueue = message_queue
        self._router: MessageRouter = message_router
        self._bridge: EventBridge = event_bridge
        self._subscriptions: Dict[str, List[Subscription]] = {}  # agent_id -> subscriptions
        self._pending_requests: Dict[str, asyncio.Future] = {}  # correlation_id -> future
        self._initialized: bool = False
        logger.info("MessageBus created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the message bus."""
        if self._initialized:
            logger.warning("MessageBus already initialized")
            return
        self._router.add_default_rules()
        self._initialized = True
        logger.info("MessageBus initialized")

    async def shutdown(self) -> None:
        """Shut down the message bus."""
        if not self._initialized:
            return
        self._subscriptions.clear()
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()
        self._initialized = False
        logger.info("MessageBus shutdown complete")

    # ── Subscribe / Unsubscribe ──

    def subscribe(self, agent_id: str, topic_pattern: str,
                  handler: Optional[Callable[..., Any]] = None) -> Subscription:
        """Subscribe an agent to messages matching a topic pattern.

        Args:
            agent_id: The subscribing agent's ID.
            topic_pattern: Regex pattern for topic matching.
            handler: Optional async callback for received messages.

        Returns:
            The created subscription.
        """
        sub = Subscription(
            agent_id=agent_id,
            topic_pattern=topic_pattern,
            handler=handler,
        )
        self._subscriptions.setdefault(agent_id, []).append(sub)
        logger.debug("Agent '%s' subscribed to '%s'", agent_id, topic_pattern)
        return sub

    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove a subscription.

        Args:
            subscription_id: The subscription to remove.

        Returns:
            True if removed successfully.
        """
        for agent_id, subs in self._subscriptions.items():
            for sub in subs:
                if sub.subscription_id == subscription_id:
                    subs.remove(sub)
                    logger.debug("Subscription removed: %s", subscription_id)
                    return True
        return False

    # ── Publish ──

    async def publish(self, message: Message) -> int:
        """Publish a message to all matching subscribers.

        Args:
            message: The message to publish.

        Returns:
            Number of agents the message was delivered to.
        """
        if not self._initialized:
            raise RuntimeError("MessageBus not initialized")

        # Route the message
        routing = self._router.route(message.topic, message.sender_id, message.payload)
        action = next(iter(routing.keys()), RoutingAction.DELIVER)
        targets = routing.get(action, [])

        if action == RoutingAction.DROP:
            logger.debug("Message dropped by router: %s", message.topic)
            return 0

        delivered = 0

        if action == RoutingAction.BROADCAST:
            # Deliver to all subscribers matching the topic
            for agent_id, subs in self._subscriptions.items():
                if agent_id == message.sender_id:
                    continue
                for sub in subs:
                    if sub.matches_topic(message.topic):
                        self._deliver_to_subscriber(sub, message)
                        delivered += 1
        else:
            # Deliver to specific targets
            for target_id in targets:
                subs = self._subscriptions.get(target_id, [])
                for sub in subs:
                    if sub.matches_topic(message.topic):
                        self._deliver_to_subscriber(sub, message)
                        delivered += 1

        # Also enqueue for persistent delivery
        item = QueueItem(
            topic=message.topic,
            payload=message.to_dict(),
            priority=QueuePriority.NORMAL,
            sender_id=message.sender_id,
            ttl_seconds=message.ttl_seconds,
        )
        await self._queue.enqueue(item)

        # Emit event
        await self._bridge.publish(
            self._bridge.__class__.__module__  # Placeholder
        )

        logger.debug("Message published: %s -> %d agents", message.topic, delivered)
        return delivered

    async def broadcast(self, message: Message) -> int:
        """Broadcast a message to all agents.

        Args:
            message: The message to broadcast.

        Returns:
            Number of agents the message was delivered to.
        """
        message.msg_type = MessageType.BROADCAST
        return await self.publish(message)

    # ── Request / Response ──

    async def request(
        self, message: Message, timeout_seconds: float = 10.0,
    ) -> Optional[Message]:
        """Send a request and wait for a response.

        Args:
            message: The request message.
            timeout_seconds: Maximum wait time for response.

        Returns:
            The response message, or None if timeout.
        """
        message.msg_type = MessageType.REQUEST
        message.correlation_id = message.message_id

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_requests[message.correlation_id] = future

        try:
            await self.publish(message)
            response = await asyncio.wait_for(future, timeout=timeout_seconds)
            return response
        except asyncio.TimeoutError:
            logger.warning("Request timeout: %s", message.correlation_id)
            return None
        finally:
            self._pending_requests.pop(message.correlation_id, None)

    async def respond(self, request_message: Message, payload: Dict[str, Any]) -> None:
        """Send a response to a request.

        Args:
            request_message: The original request message.
            payload: Response payload.
        """
        if not request_message.correlation_id:
            logger.warning("Cannot respond to message without correlation_id")
            return

        response = Message(
            msg_type=MessageType.RESPONSE,
            topic=f"{request_message.topic}.response",
            sender_id="",  # Will be set by caller
            payload=payload,
            correlation_id=request_message.correlation_id,
        )

        # Check if there's a pending future for this correlation
        future = self._pending_requests.get(request_message.correlation_id)
        if future and not future.done():
            future.set_result(response)
            logger.debug("Response delivered for %s", request_message.correlation_id)
        else:
            # Deliver as regular message
            await self.publish(response)

    # ── Poll ──

    async def poll(self, agent_id: str, max_messages: int = 10) -> List[Message]:
        """Poll for queued messages for an agent.

        Args:
            agent_id: The agent to poll for.
            max_messages: Maximum messages to return.

        Returns:
            List of messages for the agent.
        """
        messages: List[Message] = []
        subs = self._subscriptions.get(agent_id, [])

        for sub in subs:
            while sub.queue and len(messages) < max_messages:
                messages.append(sub.queue.pop(0))

        return messages

    # ── Stream ──

    async def stream(
        self, topic: str, agent_id: str,
    ) -> "asyncio.Queue[Message]":
        """Create an async stream for continuous message delivery.

        Args:
            topic: Topic to stream.
            agent_id: Subscribing agent ID.

        Returns:
            An asyncio.Queue that receives matching messages.
        """
        stream_queue: asyncio.Queue[Message] = asyncio.Queue()

        async def stream_handler(msg: Message) -> None:
            await stream_queue.put(msg)

        self.subscribe(agent_id, topic, handler=stream_handler)
        logger.debug("Stream created for agent '%s' on topic '%s'", agent_id, topic)
        return stream_queue

    # ── Helpers ──

    def _deliver_to_subscriber(self, sub: Subscription, message: Message) -> None:
        """Deliver a message to a subscriber.

        Args:
            sub: The subscription to deliver to.
            message: The message to deliver.
        """
        if sub.handler:
            try:
                if asyncio.iscoroutinefunction(sub.handler):
                    asyncio.create_task(sub.handler(message))
                else:
                    sub.handler(message)
            except Exception:
                logger.exception("Handler failed for subscription %s", sub.subscription_id)
        else:
            sub.queue.append(message)

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the message bus state.

        Returns:
            Dict with subscription and pending request counts.
        """
        total_subs = sum(len(s) for s in self._subscriptions.values())
        return {
            "initialized": self._initialized,
            "total_subscriptions": total_subs,
            "agents_subscribed": len(self._subscriptions),
            "pending_requests": len(self._pending_requests),
            "queue_depth": self._queue.depth,
        }
