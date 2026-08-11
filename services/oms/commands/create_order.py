"""CreateOrderCommand — create a new order in the OMS."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .order_command import OrderCommand
from .command_metadata import CommandMetadata


@dataclass
class CreateOrderCommand(OrderCommand):
    """Command to create a new order.

    This is the only command where order_id is empty — the OMS
    allocates a new order_id upon creation.
    """

    metadata: CommandMetadata = field(default_factory=CommandMetadata)
    order_id: str = ""  # empty — allocated by OMS
    expected_version: Optional[int] = None

    # ── Order fields ───────────────────────────────
    client_order_id: str = ""
    symbol: str = ""
    side: str = ""  # BUY / SELL
    order_type: str = ""  # MARKET / LIMIT / etc.
    quantity: float = 0.0
    price: float = 0.0
    time_in_force: str = "DAY"

    # ── Control lineage ────────────────────────────
    certificate_id: str = ""
    lineage_id: str = ""
    flow_id: str = ""
    decision_id: str = ""
    order_intent_id: str = ""

    # ── Account ────────────────────────────────────
    account_id: str = ""
    strategy_id: str = ""

    # ── Optional ───────────────────────────────────
    parent_order_id: str = ""
    root_order_id: str = ""
    expires_at: Optional[float] = None

    @property
    def command_type(self) -> str:
        return "CREATE_ORDER"

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "client_order_id": self.client_order_id,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "price": self.price,
            "time_in_force": self.time_in_force,
            "certificate_id": self.certificate_id,
            "lineage_id": self.lineage_id,
            "flow_id": self.flow_id,
            "decision_id": self.decision_id,
            "order_intent_id": self.order_intent_id,
            "account_id": self.account_id,
            "strategy_id": self.strategy_id,
            "parent_order_id": self.parent_order_id,
            "root_order_id": self.root_order_id,
            "expires_at": self.expires_at,
        })
        return d
