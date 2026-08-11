"""OrderId value object — unique order identifier."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class OrderId:
    """Institutional order identifier.

    Format: ORD-YYYYMMDD-NNNNNN
    """

    order_id: str = field(
        default_factory=lambda: f"ORD-{__import__('uuid').uuid4().hex[:12].upper()}"
    )
    client_order_id: str = ""
    parent_order_id: str = ""
    root_order_id: str = ""

    @classmethod
    def create(cls, client_order_id: str = "",
               parent_order_id: str = "",
               root_order_id: str = "") -> OrderId:
        return cls(
            client_order_id=client_order_id,
            parent_order_id=parent_order_id,
            root_order_id=root_order_id,
        )

    @classmethod
    def with_children(cls, order_id: str, parent_id: str,
                      root_id: str) -> OrderId:
        """Create a child order identity linked to parent."""
        return cls(
            order_id=order_id,
            parent_order_id=parent_id,
            root_order_id=root_id or parent_id,
        )

    @property
    def is_child(self) -> bool:
        return bool(self.parent_order_id)

    @property
    def display(self) -> str:
        return self.order_id

    def __str__(self) -> str:
        return self.order_id

    def __hash__(self) -> int:
        return hash(self.order_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OrderId):
            return NotImplemented
        return self.order_id == other.order_id
