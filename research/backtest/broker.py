from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from research.strategy.context import StrategyContext


@dataclass
class Order:
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float = 0.0
    status: str = "CREATED"
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class Fill:
    fill_id: str
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    cash_change: float
    filled_at: datetime = None

    def __post_init__(self):
        if self.filled_at is None:
            self.filled_at = datetime.utcnow()


class BacktestBroker:
    def __init__(self, context: StrategyContext):
        self.context = context
        self._orders = {}
        self._fills = {}
        self._commission_rate = 0.0001

    def submit_order(self, symbol: str, side: str, quantity: float, price: float = 0.0) -> Order:
        order_id = f"order_{len(self._orders) + 1}_{datetime.utcnow().timestamp()}"
        
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            status="SUBMITTED",
        )
        
        self._orders[order_id] = order
        return order

    def execute_order(self, order: Order, current_price: float) -> Optional[Fill]:
        if order.status != "SUBMITTED":
            return None

        fill_price = current_price if order.price == 0 else order.price
        commission = fill_price * order.quantity * self._commission_rate
        
        if order.side == "BUY":
            total_cost = fill_price * order.quantity + commission
            if self.context.cash < total_cost:
                return None
            self.context.update_cash(-total_cost)
            self.context.update_position(order.symbol, order.quantity)
            cash_change = -total_cost
        else:
            total_revenue = fill_price * order.quantity - commission
            if self.context.get_position(order.symbol) < order.quantity:
                return None
            self.context.update_cash(total_revenue)
            self.context.update_position(order.symbol, -order.quantity)
            cash_change = total_revenue

        fill_id = f"fill_{len(self._fills) + 1}_{datetime.utcnow().timestamp()}"
        fill = Fill(
            fill_id=fill_id,
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            cash_change=cash_change,
        )

        order.status = "FILLED"
        self._fills[fill_id] = fill

        return fill

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def get_all_orders(self) -> Dict[str, Order]:
        return dict(self._orders)

    def get_all_fills(self) -> Dict[str, Fill]:
        return dict(self._fills)

    def set_commission_rate(self, rate: float):
        self._commission_rate = rate