"""RequestCancelCommand — request cancellation of an order."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .order_command import OrderCommand
from .command_metadata import CommandMetadata


@dataclass
class RequestCancelCommand(OrderCommand):
    """Command to request cancellation.

    This does NOT immediately cancel the order. It generates an
    ORDER_CANCEL_REQUESTED event, and the order stays in WORKING
    until ConfirmCancelCommand is received.
    """

    metadata: CommandMetadata = field(default_factory=CommandMetadata)
    order_id: str = ""
    expected_version: Optional[int] = None

    reason: str = ""
    cancel_quantity: float = 0.0  # 0 = cancel all remaining

    @property
    def command_type(self) -> str:
        return "REQUEST_CANCEL"

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "reason": self.reason,
            "cancel_quantity": self.cancel_quantity,
        })
        return d
