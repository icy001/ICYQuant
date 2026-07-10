from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Trade:
    symbol: str
    entry_price: float
    quantity: int
    strategy: str
    time: datetime
    trade_id: str = field(default="")
    exit_price: Optional[float] = None
    pnl: Optional[float] = None

    def __post_init__(self):
        if isinstance(self.time, str):
            self.time = datetime.fromisoformat(self.time)