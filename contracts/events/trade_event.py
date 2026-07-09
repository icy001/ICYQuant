from datetime import datetime
from enum import Enum


class TradeEventType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeEvent:
    def __init__(
        self,
        event_id: str,
        type: TradeEventType,
        symbol: str,
        quantity: float,
        timestamp: datetime = None,
    ) -> None:
        self.event_id = event_id
        self.type = type
        self.symbol = symbol
        self.quantity = quantity
        self.timestamp = timestamp or datetime.utcnow()
