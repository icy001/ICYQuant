from dataclasses import dataclass
from datetime import datetime

from .base_event import BaseEvent


@dataclass
class OrderCreatedEvent(BaseEvent):
    symbol: str
    side: str
    quantity: float
    price: float

    def __init__(
        self,
        event_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        timestamp: datetime = None,
    ) -> None:
        super().__init__(
            event_id=event_id,
            timestamp=timestamp or datetime.utcnow(),
        )
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.price = price


@dataclass
class OrderSubmittedEvent(BaseEvent):
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
class OrderFilledEvent(BaseEvent):
    order_id: str
    symbol: str
    quantity: float
    price: float

    def __init__(
        self,
        event_id: str,
        symbol: str,
        quantity: float,
        price: float,
        timestamp: datetime = None,
    ) -> None:
        super().__init__(
            event_id=event_id,
            timestamp=timestamp or datetime.utcnow(),
        )
        self.order_id = event_id
        self.symbol = symbol
        self.quantity = quantity
        self.price = price


@dataclass
class OrderCancelledEvent(BaseEvent):
    order_id: str
    symbol: str

    def __init__(
        self,
        event_id: str,
        symbol: str,
        timestamp: datetime = None,
    ) -> None:
        super().__init__(
            event_id=event_id,
            timestamp=timestamp or datetime.utcnow(),
        )
        self.order_id = event_id
        self.symbol = symbol


@dataclass
class OrderRejectedEvent(BaseEvent):
    order_id: str
    symbol: str
    reason: str

    def __init__(
        self,
        event_id: str,
        symbol: str,
        reason: str,
        timestamp: datetime = None,
    ) -> None:
        super().__init__(
            event_id=event_id,
            timestamp=timestamp or datetime.utcnow(),
        )
        self.order_id = event_id
        self.symbol = symbol
        self.reason = reason
