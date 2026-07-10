from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Order:
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float = 0.0
    status: str = "CREATED"
    created_at: datetime = field(default_factory=lambda: datetime.utcnow())