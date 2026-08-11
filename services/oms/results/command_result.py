"""CommandResult — unified result of command processing."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class CommandResult:
    """The result of processing a command.

    A successful result carries the order_id, event_id, event_sequence,
    and the new order status. A failed result carries an error_code
    and error_message.

    CommandResults are cached by command_id for idempotency —
    duplicate commands return the original result.
    """

    command_id: str = ""
    success: bool = False
    order_id: str = ""
    event_id: str = ""
    event_sequence: int = 0
    status: str = ""
    error_code: str = ""
    error_message: str = ""
    timestamp: float = field(default_factory=lambda: __import__("time").time())
    idempotent: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, command_id: str, order_id: str,
           event_id: str = "", event_sequence: int = 0,
           status: str = "", **extra: Any) -> "CommandResult":
        return cls(
            command_id=command_id,
            success=True,
            order_id=order_id,
            event_id=event_id,
            event_sequence=event_sequence,
            status=status,
            extra=dict(extra),
        )

    @classmethod
    def fail(cls, command_id: str, error_code: str,
             error_message: str = "",
             order_id: str = "") -> "CommandResult":
        return cls(
            command_id=command_id,
            success=False,
            order_id=order_id,
            error_code=error_code,
            error_message=error_message,
        )

    @classmethod
    def idempotent_replay(cls, original: "CommandResult") -> "CommandResult":
        """Create a result indicating idempotent replay of a command."""
        return cls(
            command_id=original.command_id,
            success=original.success,
            order_id=original.order_id,
            event_id=original.event_id,
            event_sequence=original.event_sequence,
            status=original.status,
            error_code=original.error_code,
            error_message=original.error_message,
            idempotent=True,
            extra=dict(original.extra),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "success": self.success,
            "order_id": self.order_id,
            "event_id": self.event_id,
            "event_sequence": self.event_sequence,
            "status": self.status,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "timestamp": self.timestamp,
            "idempotent": self.idempotent,
            "extra": dict(self.extra),
        }
