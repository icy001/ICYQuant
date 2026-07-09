from dataclasses import dataclass
from datetime import datetime


@dataclass
class OrderCreatedEvent:
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float = 0.0
    timestamp: datetime = None

    def __init__(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float = 0.0,
        timestamp: datetime = None,
    ) -> None:
        self.order_id = order_id
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.price = price
        self.timestamp = timestamp or datetime.utcnow()


@dataclass
class OrderSubmittedEvent:
    order_id: str
    symbol: str
    timestamp: datetime = None

    def __init__(
        self,
        order_id: str,
        symbol: str,
        timestamp: datetime = None,
    ) -> None:
        self.order_id = order_id
        self.symbol = symbol
        self.timestamp = timestamp or datetime.utcnow()


@dataclass
class OrderFilledEvent:
    order_id: str
    symbol: str
    quantity: float
    price: float
    timestamp: datetime = None

    def __init__(
        self,
        order_id: str,
        symbol: str,
        quantity: float,
        price: float,
        timestamp: datetime = None,
    ) -> None:
        self.order_id = order_id
        self.symbol = symbol
        self.quantity = quantity
        self.price = price
        self.timestamp = timestamp or datetime.utcnow()


@dataclass
class OrderCancelledEvent:
    order_id: str
    symbol: str
    timestamp: datetime = None

    def __init__(
        self,
        order_id: str,
        symbol: str,
        timestamp: datetime = None,
    ) -> None:
        self.order_id = order_id
        self.symbol = symbol
        self.timestamp = timestamp or datetime.utcnow()


@dataclass
class OrderRejectedEvent:
    order_id: str
    symbol: str
    reason: str
    timestamp: datetime = None

    def __init__(
        self,
        order_id: str,
        symbol: str,
        reason: str,
        timestamp: datetime = None,
    ) -> None:
        self.order_id = order_id
        self.symbol = symbol
        self.reason = reason
        self.timestamp = timestamp or datetime.utcnow()