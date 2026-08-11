"""ApplyExecutionCommand — apply an execution fill to an order."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .order_command import OrderCommand
from .command_metadata import CommandMetadata


@dataclass
class ApplyExecutionCommand(OrderCommand):
    """Command to apply an execution fill.

    This is one of the most critical commands — it carries an
    execution_id that must be unique. Duplicate execution_ids
    with the same payload are idempotent replays; with different
    payloads they are conflicts.

    The command does NOT decide whether the fill is partial or full —
    the aggregate determines that based on remaining quantity.
    """

    metadata: CommandMetadata = field(default_factory=CommandMetadata)
    order_id: str = ""
    expected_version: Optional[int] = None

    execution_id: str = ""
    fill_quantity: float = 0.0
    fill_price: float = 0.0
    execution_timestamp: float = 0.0

    @property
    def command_type(self) -> str:
        return "APPLY_EXECUTION"

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "execution_id": self.execution_id,
            "fill_quantity": self.fill_quantity,
            "fill_price": self.fill_price,
            "execution_timestamp": self.execution_timestamp,
        })
        return d
