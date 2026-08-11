"""ConfirmCancelCommand — confirm cancellation after execution gateway ACK."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .order_command import OrderCommand
from .command_metadata import CommandMetadata


@dataclass
class ConfirmCancelCommand(OrderCommand):
    """Command to confirm cancellation.

    Sent by the execution gateway after the venue confirms the cancel.
    Generates an ORDER_CANCELLED event.
    """

    metadata: CommandMetadata = field(default_factory=CommandMetadata)
    order_id: str = ""
    expected_version: Optional[int] = None

    cancelled_quantity: float = 0.0
    reason: str = ""

    @property
    def command_type(self) -> str:
        return "CONFIRM_CANCEL"

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "cancelled_quantity": self.cancelled_quantity,
            "reason": self.reason,
        })
        return d
