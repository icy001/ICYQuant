from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

from research.strategy.context import StrategyContext
from research.portfolio.portfolio import Portfolio

from .order import Order


@dataclass
class BacktestContext(StrategyContext):
    portfolio: Optional[Portfolio] = None
    orders: Dict[str, Order] = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()
        if self.portfolio is None:
            self.portfolio = Portfolio(initial_cash=self.cash)

    @property
    def cash(self):
        if self.portfolio is not None:
            return self.portfolio.cash
        return self.__dict__.get("_cash", 0.0)

    @cash.setter
    def cash(self, value):
        if self.portfolio is not None:
            self.portfolio.cash = value
        else:
            self.__dict__["_cash"] = value

    @property
    def positions(self):
        if self.portfolio is not None:
            return {k: v.quantity for k, v in self.portfolio.holdings.positions.items()}
        return self.__dict__.get("_positions", {})

    @positions.setter
    def positions(self, value):
        if self.portfolio is not None:
            for symbol, quantity in value.items():
                pos = self.portfolio.holdings.get_position(symbol)
                pos.quantity = quantity
        else:
            self.__dict__["_positions"] = value

    def update_position(self, symbol: str, quantity: float) -> None:
        if self.portfolio is not None:
            pos = self.portfolio.holdings.get_position(symbol)
            pos.quantity += quantity
        else:
            super().update_position(symbol, quantity)

    def get_position(self, symbol: str) -> float:
        if self.portfolio is not None:
            pos = self.portfolio.holdings.get_position(symbol)
            return pos.quantity
        return super().get_position(symbol)

    def update_cash(self, amount: float) -> None:
        if self.portfolio is not None:
            self.portfolio.cash += amount
        else:
            super().update_cash(amount)

    def buy(self, symbol: str, quantity: float) -> Order:
        order_id = f"order_{len(self.orders) + 1}_{datetime.utcnow().timestamp()}"
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side="BUY",
            quantity=quantity,
            status="CREATED",
        )
        self.orders[order_id] = order
        return order

    def sell(self, symbol: str, quantity: float) -> Order:
        order_id = f"order_{len(self.orders) + 1}_{datetime.utcnow().timestamp()}"
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side="SELL",
            quantity=quantity,
            status="CREATED",
        )
        self.orders[order_id] = order
        return order