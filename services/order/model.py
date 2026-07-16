from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from .enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    TimeInForce,
)


@dataclass
class Order:

    symbol: str
    side: OrderSide
    quantity: Decimal

    order_type: OrderType = OrderType.MARKET

    limit_price: Decimal | None = None

    stop_price: Decimal | None = None

    time_in_force: TimeInForce = TimeInForce.DAY

    order_id: UUID = field(default_factory=uuid4)

    status: OrderStatus = OrderStatus.NEW

    filled_quantity: Decimal = Decimal("0")

    average_price: Decimal = Decimal("0")

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def remaining_quantity(self) -> Decimal:
        return self.quantity - self.filled_quantity

    @property
    def is_completed(self) -> bool:
        return self.status in (
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        )