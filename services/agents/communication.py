"""Agent Communication - high-level messaging patterns between agents.

Provides agent-to-agent communication protocols:
- Request/Response pattern
- Publish/Subscribe
- Alert broadcasting
- Committee deliberation (multi-agent consensus)
"""

import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from infrastructure.agents.message_bus import MessageBus, Message, MessageType, MessagePriority

logger = logging.getLogger(__name__)


class CommunicationPattern(Enum):
    DIRECT = "direct"
    BROADCAST = "broadcast"
    REQUEST_REPLY = "request_reply"
    PUBLISH_SUBSCRIBE = "publish_subscribe"
    COMMITTEE = "committee"


@dataclass
class AgentMessage:
    """High-level message wrapper for agent communication."""

    msg_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    sender: str = ""
    recipients: List[str] = field(default_factory=list)
    event: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    pattern: CommunicationPattern = CommunicationPattern.DIRECT
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    requires_response: bool = False
    timeout: float = 30.0
    _response: Optional[Dict[str, Any]] = None
    _response_callback: Optional[Callable] = None

    def to_bus_message(self) -> Message:
        """Convert to infrastructure Message."""
        return Message(
            msg_type=MessageType.EVENT if not self.requires_response else MessageType.REQUEST,
            sender=self.sender,
            recipient=self.recipients[0] if self.recipients else "*",
            event=self.event,
            data=self.data,
            priority=self.priority,
        )


class AgentCommunicator:
    """High-level communication handler for agents.

    Wraps the infrastructure MessageBus with agent-specific patterns.
    """

    def __init__(self, agent_name: str, message_bus: Optional[MessageBus] = None):
        self.agent_name = agent_name
        self.message_bus = message_bus or MessageBus()
        self._handlers: Dict[str, Callable] = {}
        self._sent_messages: List[AgentMessage] = []
        self._received_messages: List[Message] = []
        self._max_history = 1000

        # Subscribe to own messages
        self.message_bus.subscribe(self.agent_name, self._on_message)

    def _on_message(self, msg: Message) -> None:
        """Handle incoming bus message."""
        self._received_messages.append(msg)
        if len(self._received_messages) > self._max_history:
            self._received_messages = self._received_messages[-self._max_history:]

        # Dispatch to registered handlers
        handler = self._handlers.get(msg.event)
        if handler:
            try:
                handler(msg.data)
            except Exception:
                logger.exception("Handler error for event %s", msg.event)

    def register_handler(self, event: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        """Register a handler for a specific event type."""
        self._handlers[event] = handler

    def send(
        self,
        recipient: str,
        event: str,
        data: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> str:
        """Send a direct message to another agent."""
        msg = AgentMessage(
            sender=self.agent_name,
            recipients=[recipient],
            event=event,
            data=data,
            pattern=CommunicationPattern.DIRECT,
            priority=priority,
        )
        self._sent_messages.append(msg)
        self.message_bus.publish(msg.to_bus_message())
        logger.debug("[%s] -> [%s] : %s", self.agent_name, recipient, event)
        return msg.msg_id

    def broadcast(
        self,
        event: str,
        data: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> str:
        """Broadcast a message to all agents."""
        msg = AgentMessage(
            sender=self.agent_name,
            recipients=["*"],
            event=event,
            data=data,
            pattern=CommunicationPattern.BROADCAST,
            priority=priority,
        )
        self._sent_messages.append(msg)
        self.message_bus.publish(msg.to_bus_message())
        logger.debug("[%s] >> BROADCAST : %s", self.agent_name, event)
        return msg.msg_id

    def request(
        self,
        recipient: str,
        event: str,
        data: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Optional[Dict[str, Any]]:
        """Send a request and wait for response."""
        response = self.message_bus.send_request(
            recipient=recipient,
            event=event,
            data=data,
            sender=self.agent_name,
            timeout=timeout,
        )
        if response:
            return response.data
        return None

    def reply(
        self,
        request: Message,
        event: str,
        data: Dict[str, Any],
    ) -> None:
        """Reply to a request."""
        self.message_bus.send_response(request, event, data)

    def send_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "warning",
        data: Dict[str, Any] = None,
    ) -> str:
        """Send an alert to all agents."""
        return self.broadcast(
            event=f"ALERT_{alert_type.upper()}",
            data={
                "type": alert_type,
                "message": message,
                "severity": severity,
                "data": data or {},
            },
            priority=MessagePriority.HIGH,
        )

    # ── Committee Deliberation ──────────────────────────────────

    def deliberate(
        self,
        members: List[str],
        proposal: str,
        data: Dict[str, Any],
        timeout: float = 60.0,
    ) -> Dict[str, Any]:
        """Run a committee deliberation - ask all members and collect votes.

        Returns aggregated result with individual votes.
        """
        votes: Dict[str, Dict[str, Any]] = {}
        for member in members:
            response = self.request(
                recipient=member,
                event="COMMITTEE_VOTE",
                data={"proposal": proposal, **data},
                timeout=timeout / max(1, len(members)),
            )
            if response:
                votes[member] = response

        # Aggregate votes
        approvals = sum(1 for v in votes.values() if v.get("vote") == "approve")
        rejections = sum(1 for v in votes.values() if v.get("vote") == "reject")
        abstentions = sum(1 for v in votes.values() if v.get("vote") == "abstain")

        total = approvals + rejections + abstentions
        approved = approvals > rejections if total > 0 else False

        return {
            "proposal": proposal,
            "approved": approved,
            "votes": votes,
            "summary": {
                "approve": approvals,
                "reject": rejections,
                "abstain": abstentions,
                "total": total,
            },
        }

    # ── Query Methods ───────────────────────────────────────────

    def get_received(
        self,
        sender: Optional[str] = None,
        event: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get received messages with optional filters."""
        results = []
        for msg in reversed(self._received_messages):
            if sender and msg.sender != sender:
                continue
            if event and msg.event != event:
                continue
            results.append(msg.to_dict())
            if len(results) >= limit:
                break
        return list(reversed(results))

    def get_sent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get sent messages."""
        return [
            {
                "msg_id": m.msg_id,
                "recipients": m.recipients,
                "event": m.event,
                "pattern": m.pattern.value,
                "timestamp": m.timestamp,
            }
            for m in self._sent_messages[-limit:]
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get communication statistics."""
        return {
            "sent_count": len(self._sent_messages),
            "received_count": len(self._received_messages),
            "handlers": list(self._handlers.keys()),
        }

    def clear(self) -> None:
        """Clear communication history."""
        self._sent_messages.clear()
        self._received_messages.clear()
