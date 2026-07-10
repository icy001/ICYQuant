from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4
from typing import Optional


class OrderStatus(Enum):
    NEW = "NEW"
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


@dataclass
class Order:
    symbol: str
    side: Side
    quantity: float
    order_id: UUID = field(default_factory=uuid4)
    order_type: OrderType = OrderType.MARKET
    price: float = 0.0
    status: OrderStatus = OrderStatus.NEW
    created_at: datetime = field(default_factory=lambda: datetime.utcnow())
    filled_quantity: float = 0.0

    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    def is_active(self) -> bool:
        return self.status in (OrderStatus.NEW, OrderStatus.ACCEPTED, OrderStatus.PARTIALLY_FILLED)