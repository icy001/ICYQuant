"""
ICYQuant Agent Message — structured inter-agent communication messages.

Defines message types, envelopes, and serialization for communication
between agents in the multi-agent quant collaboration system.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """Kinds of inter-agent messages."""
    # Task
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    TASK_CANCEL = "task_cancel"
    TASK_PROGRESS = "task_progress"

    # Query
    QUERY = "query"
    QUERY_RESPONSE = "query_response"

    # Deliberation
    OPINION = "opinion"
    VOTE = "vote"
    DEBATE = "debate"
    CONSENSUS = "consensus"

    # System
    HEARTBEAT = "heartbeat"
    STATUS = "status"
    ERROR = "error"
    NOTIFICATION = "notification"

    # Data
    DATA_REQUEST = "data_request"
    DATA_RESPONSE = "data_response"

    # Control
    COMMAND = "command"
    ACK = "ack"


class MessagePriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class MessageEnvelope:
    """Envelope wrapping a message with routing and metadata."""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    msg_type: MessageType = MessageType.NOTIFICATION
    priority: MessagePriority = MessagePriority.MEDIUM

    # Routing
    sender_id: str = ""
    recipient_id: str = ""         # "" = broadcast
    correlation_id: str = ""       # Links request/response pairs
    topic: str = ""                # Topic for pub/sub routing
    reply_to: str = ""             # Queue to send response to

    # Content
    payload: Any = None
    content_type: str = "application/json"

    # Timing
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    ttl_seconds: int = 300

    # Tracing
    trace_id: str = ""
    span_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) >= self.expires_at

    def is_broadcast(self) -> bool:
        return not self.recipient_id

    @classmethod
    def reply_to(cls, original: MessageEnvelope, payload: Any,
                 msg_type: Optional[MessageType] = None) -> MessageEnvelope:
        """Create a reply envelope linked to the original message."""
        return cls(
            msg_type=msg_type or MessageType.QUERY_RESPONSE,
            recipient_id=original.sender_id,
            correlation_id=original.message_id,
            trace_id=original.trace_id,
            payload=payload,
        )


@dataclass
class TaskMessage:
    """Structured task request/response between agents."""
    task_id: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class OpinionMessage:
    """An agent's opinion for debate/consensus."""
    opinion_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    author_id: str = ""
    topic: str = ""
    stance: str = ""               # "agree", "disagree", "neutral"
    reasoning: str = ""
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)


@dataclass
class VoteMessage:
    """A vote cast in a consensus round."""
    vote_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    voter_id: str = ""
    proposal_id: str = ""
    choice: str = ""               # "approve", "reject", "abstain"
    weight: float = 1.0
    rationale: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ErrorMessage:
    """Structured error response."""
    error_code: str = ""
    error_message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    recoverable: bool = False
    retry_after_seconds: int = 0


class MessageSerializer:
    """Serialize/deserialize message envelopes between agents."""

    @staticmethod
    def serialize(envelope: MessageEnvelope) -> dict[str, Any]:
        return {
            "message_id": envelope.message_id,
            "msg_type": envelope.msg_type.value,
            "priority": envelope.priority.value,
            "sender_id": envelope.sender_id,
            "recipient_id": envelope.recipient_id,
            "correlation_id": envelope.correlation_id,
            "topic": envelope.topic,
            "reply_to": envelope.reply_to,
            "payload": envelope.payload,
            "content_type": envelope.content_type,
            "created_at": envelope.created_at.isoformat(),
            "expires_at": envelope.expires_at.isoformat() if envelope.expires_at else None,
            "ttl_seconds": envelope.ttl_seconds,
            "trace_id": envelope.trace_id,
            "span_id": envelope.span_id,
            "metadata": envelope.metadata,
        }

    @staticmethod
    def deserialize(data: dict[str, Any]) -> MessageEnvelope:
        expires_at = data.get("expires_at")
        return MessageEnvelope(
            message_id=data.get("message_id", str(uuid.uuid4())),
            msg_type=MessageType(data.get("msg_type", "notification")),
            priority=MessagePriority(data.get("priority", "medium")),
            sender_id=data.get("sender_id", ""),
            recipient_id=data.get("recipient_id", ""),
            correlation_id=data.get("correlation_id", ""),
            topic=data.get("topic", ""),
            reply_to=data.get("reply_to", ""),
            payload=data.get("payload"),
            content_type=data.get("content_type", "application/json"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(timezone.utc),
            expires_at=datetime.fromisoformat(str(expires_at)) if expires_at else None,
            ttl_seconds=data.get("ttl_seconds", 300),
            trace_id=data.get("trace_id", ""),
            span_id=data.get("span_id", ""),
            metadata=data.get("metadata", {}),
        )
