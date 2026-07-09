from dataclasses import dataclass
from datetime import datetime

from .base_event import BaseEvent


@dataclass
class TradeEvent(BaseEvent):
    symbol: str
    side: str
    quantity: float

    def __init__(
        self,
        event_id: str,
        symbol: str,
        side: str,
        quantity: float,
        timestamp: datetime = None,
    ) -> None:
        super().__init__(
            event_id=event_id,
            timestamp=timestamp or datetime.utcnow(),
        )
        self.symbol = symbol
        self.side = side
        self.quantity = quantity

    def apply(
        self,
        position: float,
    ) -> float:
        if self.side == "BUY":
            return position + self.quantity
        if self.side == "SELL":
            return position - self.quantity
        return position
