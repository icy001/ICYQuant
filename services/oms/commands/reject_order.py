"""RejectOrderCommand — reject an order (execution reject)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .order_command import OrderCommand
from .command_metadata import CommandMetadata


@dataclass
class RejectOrderCommand(OrderCommand):
    """Command to reject an order.

    This is an execution-level reject — the order already exists in
    the OMS but the venue/broker rejected it. This is different from
    admission reject (which happens before the order enters OMS).
    """

    metadata: CommandMetadata = field(default_factory=CommandMetadata)
    order_id: str = ""
    expected_version: Optional[int] = None

    reject_code: str = ""
    reject_reason: str = ""
    execution_source: str = ""

    @property
    def command_type(self) -> str:
        return "REJECT_ORDER"

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "reject_code": self.reject_code,
            "reject_reason": self.reject_reason,
            "execution_source": self.execution_source,
        })
        return d
