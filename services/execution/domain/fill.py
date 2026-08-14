from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ExecutionFill:
    execution_id: str

    execution_request_id: str
    order_id: str

    quantity: float
    price: float

    timestamp: datetime

    external_order_id: str | None = None

    venue_id: str | None = None

    liquidity: str | None = None

    fee: float = 0.0

    currency: str | None = None

    def validate(self) -> None:

        if not self.execution_id:
            raise ValueError(
                "execution_id is required"
            )

        if self.quantity <= 0:
            raise ValueError(
                "fill quantity must be positive"
            )

        if self.price <= 0:
            raise ValueError(
                "fill price must be positive"
            )

        if self.fee < 0:
            raise ValueError(
                "fee cannot be negative"
            )
