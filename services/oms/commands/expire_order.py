"""ExpireOrderCommand — expire an order whose expires_at has passed."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .order_command import OrderCommand
from .command_metadata import CommandMetadata


@dataclass
class ExpireOrderCommand(OrderCommand):
    """Command to expire an order.

    Sent by a scheduled job or the lifecycle manager when
    current_time >= order.expires_at.
    """

    metadata: CommandMetadata = field(default_factory=CommandMetadata)
    order_id: str = ""
    expected_version: Optional[int] = None

    expired_at: float = 0.0
    reason: str = ""

    @property
    def command_type(self) -> str:
        return "EXPIRE_ORDER"

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "expired_at": self.expired_at,
            "reason": self.reason,
        })
        return d
