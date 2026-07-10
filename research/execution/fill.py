from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from .order import Side


@dataclass
class Fill:
    order_id: UUID
    symbol: str
    quantity: float
    fill_price: float
    fill_id: UUID = field(default_factory=uuid4)
    commission: float = 0.0
    slippage: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.utcnow())
    side: Side = Side.BUY