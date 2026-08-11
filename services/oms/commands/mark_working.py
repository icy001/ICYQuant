"""MarkWorkingCommand — transition order from ROUTING to WORKING."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .order_command import OrderCommand
from .command_metadata import CommandMetadata


@dataclass
class MarkWorkingCommand(OrderCommand):
    """Command to mark an order as working at the venue.

    Sent by the execution gateway after the venue accepts the order.
    """

    metadata: CommandMetadata = field(default_factory=CommandMetadata)
    order_id: str = ""
    expected_version: Optional[int] = None

    venue_order_id: str = ""
    venue: str = ""

    @property
    def command_type(self) -> str:
        return "MARK_WORKING"

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "venue_order_id": self.venue_order_id,
            "venue": self.venue,
        })
        return d
