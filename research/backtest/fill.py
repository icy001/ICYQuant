from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Fill:
    fill_id: str
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    cash_change: float
    filled_at: datetime = field(default_factory=lambda: datetime.utcnow())