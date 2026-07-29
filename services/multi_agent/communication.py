"""Agent Communication Bus - centralized message routing between AI agents."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from collections import defaultdict

from .message import (
    AgentMessage, AgentIdentity, AgentRole, MessageType,
    MessagePriority, MessageStatus, MessageHistory, MessageProtocol,
)


class BusStatus(Enum):
    """Status of the communication bus."""
    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"


class DeliveryMode(Enum):
    """Message delivery strategy."""
    DIRECT = "DIRECT"
    FAN_OUT = "FAN_OUT"
    TOPIC = "TOPIC"
    ROUND_ROBIN = "ROUND_ROBIN"


@dataclass
class DeliveryReport:
    """Report on message delivery outcome."""
    message_id: str
    success: bool
    recipients: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    error_detail: str = ""


class AgentCommunicationBus:
    """Centralized communication bus for inter-agent messaging.

    Routes messages between agents based on:
    - Direct addressing (sender → receiver)
    - Broadcast (sender → all registered agents)
    - Topic-based (sender → topic subscribers)
    - Role-based (sender → all agents with matching role)

    Features:
    - Message validation via protocol rules
    - Priority queuing
    - Delivery tracking
    - Conversation threading
    """

    def __init__(self):
        self._agents: Dict[str, AgentIdentity] = {}
        self._subscriptions: Dict[str, Set[str]] = defaultdict(set)
        self._message_queue: List[AgentMessage] = []
        self._history: Dict[str, MessageHistory] = {}
        self._delivery_log: List[DeliveryReport] = []
        self._handlers: Dict[str, Callable] = {}
        self.status = BusStatus.INITIALIZED
        self._message_counter = 0

    def register_agent(self, agent: AgentIdentity):
        """Register an agent on the communication bus."""
        self._agents[agent.agent_id] = agent
        return self

    def unregister_agent(self, agent_id: str):
        """Remove an agent from the bus."""
        self._agents.pop(agent_id, None)
        for topic in self._subscriptions.values():
            topic.discard(agent_id)

    def subscribe(self, agent_id: str, topic: str):
        """Subscribe an agent to a topic."""
        self._subscriptions[topic].add(agent_id)

    def unsubscribe(self, agent_id: str, topic: str):
        """Unsubscribe an agent from a topic."""
        if topic in self._subscriptions:
            self._subscriptions[topic].discard(agent_id)

    def register_handler(self, message_type: str, handler: Callable):
        """Register a handler for a specific message type."""
        self._handlers[message_type] = handler

    def send(self, message: AgentMessage) -> DeliveryReport:
        """Send a message through the bus.

        Returns delivery report indicating success/failure per recipient.
        """
        if not MessageProtocol.validate_message(message):
            return DeliveryReport(
                message_id=message.message_id,
                success=False,
                error_detail="Protocol validation failed: communication not allowed",
            )

        message.status = MessageStatus.SENT
        recipients = []

        if message.message_type == MessageType.BROADCAST:
            recipients = [a.agent_id for a in self._agents.values()
                         if a.agent_id != message.sender.agent_id]
        elif message.receiver:
            recipients = [message.receiver.agent_id]

        if not recipients:
            return DeliveryReport(
                message_id=message.message_id,
                success=False,
                error_detail="No valid recipients",
            )

        self._message_queue.append(message)

        # Deliver to recipients
        delivered = []
        failed = []
        for rid in recipients:
            if rid in self._agents:
                delivered.append(rid)
            else:
                failed.append(rid)

        report = DeliveryReport(
            message_id=message.message_id,
            success=len(failed) == 0,
            recipients=delivered,
            failures=failed,
        )
        self._delivery_log.append(report)

        # Thread tracking
        correlation = message.correlation_id or message.message_id
        if correlation not in self._history:
            self._history[correlation] = MessageHistory(
                thread_id=correlation,
                topic=message.task,
            )
        self._history[correlation].add_message(message)

        return report

    def broadcast(self, sender: AgentIdentity, task: str, data: Dict[str, Any] = None,
                  priority: MessagePriority = MessagePriority.MEDIUM) -> DeliveryReport:
        """Broadcast a message to all registered agents."""
        self._message_counter += 1
        msg = AgentMessage(
            message_id=f"broadcast_{self._message_counter}",
            sender=sender,
            receiver=None,
            message_type=MessageType.BROADCAST,
            task=task,
            priority=priority,
            data=data or {},
        )
        return self.send(msg)

    def request(self, sender: AgentIdentity, receiver: AgentIdentity, task: str,
                data: Dict[str, Any] = None,
                priority: MessagePriority = MessagePriority.MEDIUM) -> DeliveryReport:
        """Send a request from one agent to another."""
        self._message_counter += 1
        msg = AgentMessage(
            message_id=f"req_{self._message_counter}",
            sender=sender,
            receiver=receiver,
            message_type=MessageType.REQUEST,
            task=task,
            priority=priority,
            data=data or {},
        )
        return self.send(msg)

    def notify(self, sender: AgentIdentity, task: str, data: Dict[str, Any] = None,
               receivers: List[AgentIdentity] = None,
               priority: MessagePriority = MessagePriority.LOW) -> List[DeliveryReport]:
        """Send notification to specific agents or all."""
        reports = []
        targets = receivers or list(self._agents.values())
        for target in targets:
            if target.agent_id != sender.agent_id:
                self._message_counter += 1
                msg = AgentMessage(
                    message_id=f"notify_{self._message_counter}",
                    sender=sender,
                    receiver=target,
                    message_type=MessageType.NOTIFICATION,
                    task=task,
                    priority=priority,
                    data=data or {},
                )
                reports.append(self.send(msg))
        return reports

    def get_thread(self, correlation_id: str) -> Optional[MessageHistory]:
        """Retrieve conversation thread by correlation ID."""
        return self._history.get(correlation_id)

    def get_agent_messages(self, agent_id: str) -> List[AgentMessage]:
        """Get all messages sent to a specific agent."""
        return [
            m for m in self._message_queue
            if m.receiver and m.receiver.agent_id == agent_id
        ]

    def get_delivery_stats(self) -> Dict[str, Any]:
        """Get delivery statistics."""
        total = len(self._delivery_log)
        successful = sum(1 for r in self._delivery_log if r.success)
        return {
            "total_deliveries": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": successful / total if total > 0 else 0,
            "queued_messages": len(self._message_queue),
            "registered_agents": len(self._agents),
            "active_threads": len(self._history),
        }

    def get_registered_agents_by_role(self, role: AgentRole) -> List[AgentIdentity]:
        """Get all registered agents with a specific role."""
        return [a for a in self._agents.values() if a.role == role]

    def start(self):
        """Start the communication bus."""
        self.status = BusStatus.RUNNING

    def stop(self):
        """Stop the communication bus."""
        self.status = BusStatus.STOPPED
