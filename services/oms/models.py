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
    status: OrderStatus = OrderStatus.CREATED
    order_type: OrderType = OrderType.MARKET
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    risk_check_result: dict = field(default_factory=dict)

    def submit_to_risk(self) -> None:
        if self.status == OrderStatus.CREATED:
            self.status = OrderStatus.RISK_CHECK
            self.updated_at = datetime.utcnow()

    def approve(self) -> None:
        if self.status == OrderStatus.RISK_CHECK:
            self.status = OrderStatus.APPROVED
            self.updated_at = datetime.utcnow()

    def reject(self) -> None:
        if self.status == OrderStatus.RISK_CHECK:
            self.status = OrderStatus.REJECTED
            self.updated_at = datetime.utcnow()

    def submit(self) -> None:
        if self.status == OrderStatus.APPROVED:
            self.status = OrderStatus.SUBMITTED
            self.updated_at = datetime.utcnow()

    def acknowledge(self) -> None:
        if self.status == OrderStatus.SUBMITTED:
            self.status = OrderStatus.ACKNOWLEDGED
            self.updated_at = datetime.utcnow()

    def fill(self, quantity: float = None) -> None:
        if self.status in (OrderStatus.ACKNOWLEDGED, OrderStatus.PARTIAL_FILLED):
            if quantity is None or quantity >= self.quantity:
                self.status = OrderStatus.FILLED
            else:
                self.status = OrderStatus.PARTIAL_FILLED
            self.updated_at = datetime.utcnow()

    def cancel(self) -> None:
        if self.status in (OrderStatus.CREATED, OrderStatus.RISK_CHECK, OrderStatus.APPROVED, OrderStatus.SUBMITTED, OrderStatus.ACKNOWLEDGED):
            self.status = OrderStatus.CANCELLED
            self.updated_at = datetime.utcnow()

    def fail(self) -> None:
        if self.status in (OrderStatus.SUBMITTED, OrderStatus.ACKNOWLEDGED):
            self.status = OrderStatus.FAILED
            self.updated_at = datetime.utcnow()