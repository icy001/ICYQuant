"""Agent Message Bus - publish/subscribe messaging between agents."""

import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class MessageType(Enum):
    EVENT = "event"
    REQUEST = "request"
    RESPONSE = "response"
    COMMAND = "command"
    NOTIFICATION = "notification"
    ALERT = "alert"


@dataclass
class Message:
    """A message passed between agents."""

    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    msg_type: MessageType = MessageType.EVENT
    sender: str = ""
    recipient: str = ""
    event: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    correlation_id: Optional[str] = None
    ttl: int = 300  # seconds

    def is_expired(self) -> bool:
        return (time.time() - self.timestamp) > self.ttl

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "msg_type": self.msg_type.value,
            "sender": self.sender,
            "recipient": self.recipient,
            "event": self.event,
            "data": self.data,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
        }


class MessageBus:
    """Central message bus for agent communication.

    Supports publish/subscribe, direct messaging, and request/response patterns.
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._message_log: List[Message] = []
        self._pending_responses: Dict[str, Callable] = {}
        self._max_log_size = 10000

    def publish(self, message: Message) -> None:
        """Publish a message to all subscribers of the recipient/topic."""
        self._message_log.append(message)
        if len(self._message_log) > self._max_log_size:
            self._message_log = self._message_log[-self._max_log_size:]

        # Deliver to recipient-specific subscribers
        recipients = [message.recipient, "*"]
        for recipient in recipients:
            handlers = self._subscriptions.get(recipient, [])
            for handler in handlers:
                try:
                    handler(message)
                except Exception:
                    logger.exception("Handler error for message %s", message.message_id)

        logger.debug("Published [%s] %s -> %s : %s",
                     message.msg_type.value, message.sender,
                     message.recipient, message.event)

    def subscribe(self, topic: str, handler: Callable[[Message], None]) -> None:
        """Subscribe to messages on a topic."""
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []
        self._subscriptions[topic].append(handler)

    def unsubscribe(self, topic: str, handler: Callable[[Message], None]) -> None:
        """Unsubscribe from a topic."""
        if topic in self._subscriptions and handler in self._subscriptions[topic]:
            self._subscriptions[topic].remove(handler)

    def send_request(
        self, recipient: str, event: str, data: Dict[str, Any],
        sender: str = "", timeout: float = 30.0,
    ) -> Optional[Message]:
        """Send a request and wait for response (synchronous)."""
        request = Message(
            msg_type=MessageType.REQUEST,
            sender=sender,
            recipient=recipient,
            event=event,
            data=data,
            correlation_id=str(uuid.uuid4())[:8],
        )
        # Publish and collect matching response
        self.publish(request)
        # Look for response in recent messages
        start = time.time()
        while time.time() - start < timeout:
            for msg in reversed(self._message_log):
                if (msg.correlation_id == request.correlation_id and
                        msg.msg_type == MessageType.RESPONSE):
                    return msg
            time.sleep(0.01)
        return None

    def send_response(self, request: Message, event: str, data: Dict[str, Any]) -> Message:
        """Send a response to a request."""
        response = Message(
            msg_type=MessageType.RESPONSE,
            sender=request.recipient,
            recipient=request.sender,
            event=event,
            data=data,
            correlation_id=request.correlation_id,
        )
        self.publish(response)
        return response

    def get_messages(
        self,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
        event: Optional[str] = None,
        msg_type: Optional[MessageType] = None,
        since: Optional[float] = None,
        limit: int = 100,
    ) -> List[Message]:
        """Query message log with filters."""
        results = []
        for msg in reversed(self._message_log):
            if sender and msg.sender != sender:
                continue
            if recipient and msg.recipient != recipient:
                continue
            if event and msg.event != event:
                continue
            if msg_type and msg.msg_type != msg_type:
                continue
            if since and msg.timestamp < since:
                continue
            results.append(msg)
            if len(results) >= limit:
                break
        return list(reversed(results))

    def clear(self) -> None:
        """Clear all subscriptions and message log."""
        self._subscriptions.clear()
        self._message_log.clear()
        self._pending_responses.clear()

    @property
    def message_count(self) -> int:
        return len(self._message_log)

    @property
    def topic_count(self) -> int:
        return len(self._subscriptions)
