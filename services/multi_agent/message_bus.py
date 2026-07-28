"""Agent-to-agent communication bus."""

from __future__ import annotations


class AgentMessageBus:
    """A simple in-process message bus for inter-agent communication.

    Messages are stored in-order and can be queried by receivers.
    Future versions will support async delivery, broadcasting, and
    persistence.
    """

    def __init__(self) -> None:
        self.messages: list[dict] = []

    def send(self, message: dict) -> None:
        """Deliver a message from one agent to another.

        Args:
            message: A dict containing ``sender``, ``receiver``, and
                     ``message`` keys.
        """
        self.messages.append(message)
