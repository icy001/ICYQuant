"""Agent Message Protocol - defines structured communication between AI agents."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MessageType(Enum):
    """Type of agent message."""
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    NOTIFICATION = "NOTIFICATION"
    BROADCAST = "BROADCAST"
    DELEGATION = "DELEGATION"
    QUERY = "QUERY"
    REPORT = "REPORT"
    ALERT = "ALERT"


class MessagePriority(Enum):
    """Message priority level."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class MessageStatus(Enum):
    """Status of a message in the communication pipeline."""
    CREATED = "CREATED"
    SENT = "SENT"
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class AgentRole(Enum):
    """Role of an agent in the organization."""
    CIO = "CIO"
    RESEARCH = "RESEARCH"
    STRATEGY = "STRATEGY"
    RISK = "RISK"
    PORTFOLIO = "PORTFOLIO"
    EXECUTION = "EXECUTION"
    PERFORMANCE = "PERFORMANCE"
    LEARNING = "LEARNING"
    MARKET = "MARKET"
    CAPITAL = "CAPITAL"


@dataclass
class AgentIdentity:
    """Unique identity of an agent in the organization."""
    agent_id: str
    name: str
    role: AgentRole
    capabilities: List[str] = field(default_factory=list)
    version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role.value,
            "capabilities": self.capabilities,
            "version": self.version,
        }


@dataclass
class AgentMessage:
    """Structured message between AI agents.

    Protocol fields:
    - sender: Source agent identity
    - receiver: Target agent identity (None for broadcast)
    - task: Task description
    - context: Contextual data for the task
    - priority: Urgency level
    """

    message_id: str
    sender: AgentIdentity
    receiver: Optional[AgentIdentity]
    message_type: MessageType
    task: str
    priority: MessagePriority = MessagePriority.MEDIUM
    context: Dict[str, Any] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    reply_to: str = ""
    status: MessageStatus = MessageStatus.CREATED
    timestamp: str = ""

    def to_envelope(self) -> Dict[str, Any]:
        """Serialize message to envelope format for transport."""
        return {
            "message_id": self.message_id,
            "sender": self.sender.to_dict(),
            "receiver": self.receiver.to_dict() if self.receiver else None,
            "message_type": self.message_type.value,
            "task": self.task,
            "priority": self.priority.value,
            "context": self.context,
            "data": self.data,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "status": self.status.value,
            "timestamp": self.timestamp,
        }

    def create_reply(self, result: Dict[str, Any], receiver: Optional["AgentIdentity"] = None) -> "AgentMessage":
        """Create a reply message to this message."""
        return AgentMessage(
            message_id=f"reply_{self.message_id}",
            sender=receiver or (self.receiver if self.receiver else self.sender),
            receiver=self.sender,
            message_type=MessageType.RESPONSE,
            task=f"Reply: {self.task}",
            priority=self.priority,
            context={"original_task": self.task},
            data=result,
            correlation_id=self.correlation_id or self.message_id,
            reply_to=self.message_id,
        )

    def create_notification(self, event: str, data: Dict[str, Any]) -> "AgentMessage":
        """Create a notification message from this context."""
        return AgentMessage(
            message_id=f"notify_{self.message_id}_{event}",
            sender=self.sender,
            receiver=None,
            message_type=MessageType.NOTIFICATION,
            task=f"Notification: {event}",
            priority=MessagePriority.MEDIUM,
            context={"source_task": self.task, "event": event},
            data=data,
            correlation_id=self.message_id,
        )


@dataclass
class MessageHistory:
    """Threaded message history for agent conversations."""
    thread_id: str
    messages: List[AgentMessage] = field(default_factory=list)
    participants: List[AgentIdentity] = field(default_factory=list)
    topic: str = ""
    created_at: str = ""

    def add_message(self, msg: AgentMessage):
        self.messages.append(msg)
        if msg.sender not in self.participants:
            self.participants.append(msg.sender)
        if msg.receiver and msg.receiver not in self.participants:
            self.participants.append(msg.receiver)

    def get_conversation_chain(self) -> List[Dict[str, Any]]:
        """Get chronological conversation chain."""
        return [
            {
                "from": m.sender.name if m.sender else "system",
                "to": m.receiver.name if m.receiver else "all",
                "type": m.message_type.value,
                "task": m.task,
                "priority": m.priority.value,
            }
            for m in self.messages
        ]

    def get_decision_trail(self) -> List[Dict[str, Any]]:
        """Extract decision-making trail from history."""
        decisions = []
        for m in self.messages:
            if m.message_type == MessageType.RESPONSE and "decision" in m.data:
                decisions.append({
                    "agent": m.sender.name if m.sender else "unknown",
                    "decision": m.data["decision"],
                    "confidence": m.data.get("confidence", 0),
                    "reasoning": m.data.get("reasoning", ""),
                })
        return decisions


class MessageProtocol:
    """Validates and enriches messages according to protocol rules."""

    VALID_ROLES = {role.value for role in AgentRole}
    ALLOWED_COMMUNICATION = {
        AgentRole.CIO: {AgentRole.RESEARCH, AgentRole.STRATEGY, AgentRole.RISK, AgentRole.PORTFOLIO, AgentRole.EXECUTION, AgentRole.LEARNING},
        AgentRole.RESEARCH: {AgentRole.CIO, AgentRole.STRATEGY, AgentRole.LEARNING},
        AgentRole.STRATEGY: {AgentRole.CIO, AgentRole.RESEARCH, AgentRole.RISK, AgentRole.PORTFOLIO},
        AgentRole.RISK: {AgentRole.CIO, AgentRole.STRATEGY, AgentRole.PORTFOLIO, AgentRole.EXECUTION},
        AgentRole.PORTFOLIO: {AgentRole.CIO, AgentRole.RISK, AgentRole.EXECUTION, AgentRole.CAPITAL},
        AgentRole.EXECUTION: {AgentRole.CIO, AgentRole.RISK, AgentRole.PORTFOLIO, AgentRole.PERFORMANCE},
        AgentRole.PERFORMANCE: {AgentRole.CIO, AgentRole.EXECUTION, AgentRole.LEARNING},
        AgentRole.LEARNING: {AgentRole.CIO, AgentRole.RESEARCH, AgentRole.PERFORMANCE},
        AgentRole.MARKET: {AgentRole.RESEARCH, AgentRole.STRATEGY, AgentRole.RISK, AgentRole.CIO},
        AgentRole.CAPITAL: {AgentRole.CIO, AgentRole.PORTFOLIO},
    }

    @classmethod
    def validate_message(cls, message: AgentMessage) -> bool:
        """Validate that communication between these agents is allowed."""
        if not message.sender or not message.sender.role:
            return False
        if message.message_type == MessageType.BROADCAST:
            return True
        if not message.receiver or not message.receiver.role:
            return False
        allowed = cls.ALLOWED_COMMUNICATION.get(message.sender.role, set())
        return message.receiver.role in allowed

    @classmethod
    def get_allowed_receivers(cls, sender_role: AgentRole) -> List[AgentRole]:
        """Get list of roles this agent can communicate with."""
        return list(cls.ALLOWED_COMMUNICATION.get(sender_role, set()))
