"""StartRoutingCommand — transition order from CREATED to ROUTING."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .order_command import OrderCommand
from .command_metadata import CommandMetadata


@dataclass
class StartRoutingCommand(OrderCommand):
    """Command to start routing an order to the execution gateway."""

    metadata: CommandMetadata = field(default_factory=CommandMetadata)
    order_id: str = ""
    expected_version: Optional[int] = None

    route: str = ""
    venue: str = ""

    @property
    def command_type(self) -> str:
        return "START_ROUTING"

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({"route": self.route, "venue": self.venue})
        return d
