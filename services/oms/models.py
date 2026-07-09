from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from .state import OrderSide, OrderStatus, OrderType


@dataclass
class Order:
    symbol: str
    side: str
    quantity: float
    order_id: str = field(default_factory=lambda: str(uuid4()))
    price: float = 0.0
    status: OrderStatus = OrderStatus.NEW
    order_type: OrderType = OrderType.MARKET
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def submit(self) -> None:
        if self.status == OrderStatus.NEW:
            self.status = OrderStatus.SUBMITTED
            self.updated_at = datetime.utcnow()

    def accept(self) -> None:
        if self.status == OrderStatus.SUBMITTED:
            self.status = OrderStatus.ACCEPTED
            self.updated_at = datetime.utcnow()

    def fill(self, quantity: float = None) -> None:
        if self.status in (OrderStatus.ACCEPTED, OrderStatus.PARTIAL_FILLED):
            if quantity is None or quantity >= self.quantity:
                self.status = OrderStatus.FILLED
            else:
                self.status = OrderStatus.PARTIAL_FILLED
            self.updated_at = datetime.utcnow()

    def cancel(self) -> None:
        if self.status in (OrderStatus.NEW, OrderStatus.SUBMITTED, OrderStatus.ACCEPTED):
            self.status = OrderStatus.CANCELLED
            self.updated_at = datetime.utcnow()

    def reject(self) -> None:
        if self.status == OrderStatus.SUBMITTED:
            self.status = OrderStatus.REJECTED
            self.updated_at = datetime.utcnow()