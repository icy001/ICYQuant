"""OrderCommand — base class for all order commands."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .command_metadata import CommandMetadata


@dataclass
class OrderCommand(ABC):
    """Base class for all order commands.

    Commands represent intent — "what the system should do".
    They are validated, then translated into domain events
    that represent "what actually happened".

    All commands carry:
      - metadata: command_id, actor, correlation, causation
      - order_id: the target order (empty for CreateOrderCommand)
      - expected_version: for optimistic concurrency control
    """

    metadata: CommandMetadata = field(default_factory=CommandMetadata)
    order_id: str = ""
    expected_version: Optional[int] = None

    @property
    @abstractmethod
    def command_type(self) -> str:
        """Return the command type name."""

    @property
    def command_id(self) -> str:
        return self.metadata.command_id

    @property
    def actor_type(self) -> str:
        return self.metadata.actor_type

    @property
    def actor_id(self) -> str:
        return self.metadata.actor_id

    @property
    def correlation_id(self) -> str:
        return self.metadata.correlation_id

    @property
    def causation_id(self) -> str:
        return self.metadata.causation_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_type": self.command_type,
            "metadata": self.metadata.to_dict(),
            "order_id": self.order_id,
            "expected_version": self.expected_version,
        }
