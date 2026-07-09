from dataclasses import dataclass
from datetime import datetime

from .base_event import BaseEvent


@dataclass
class ExecutionStartedEvent(BaseEvent):
    order_id: str
    symbol: str

    def __init__(
        self,
        event_id: str,
        order_id: str,
        symbol: str,
        timestamp: datetime = None,
    ) -> None:
        super().__init__(
            event_id=event_id,
            timestamp=timestamp or datetime.utcnow(),
        )
        self.order_id = order_id
        self.symbol = symbol


@dataclass
class ExecutionCompletedEvent(BaseEvent):
    order_id: str
    symbol: str
    quantity: float
    price: float
    status: str

    def __init__(
        self,
        event_id: str,
        order_id: str,
        symbol: str,
        quantity: float,
        price: float,
        status: str,
        timestamp: datetime = None,
    ) -> None:
        super().__init__(
            event_id=event_id,
            timestamp=timestamp or datetime.utcnow(),
        )
        self.order_id = order_id
        self.symbol = symbol
        self.quantity = quantity
        self.price = price
        self.status = status


@dataclass
class ExecutionFailedEvent(BaseEvent):
    order_id: str
    symbol: str
    reason: str

    def __init__(
        self,
        event_id: str,
        order_id: str,
        symbol: str,
        reason: str,
        timestamp: datetime = None,
    ) -> None:
        super().__init__(
            event_id=event_id,
            timestamp=timestamp or datetime.utcnow(),
        )
        self.order_id = order_id
        self.symbol = symbol
        self.reason = reason
