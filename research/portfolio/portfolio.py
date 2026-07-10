from typing import Dict, List, Tuple
from datetime import datetime

from .holdings import Holdings


class Portfolio:
    def __init__(self, initial_cash: float):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.holdings = Holdings()
        self.equity_curve: List[Tuple[datetime, float]] = []

    def apply_fill(self, fill) -> None:
        position = self.holdings.get_position(fill.symbol)
        
        if fill.quantity > 0:
            position.increase(fill.quantity, fill.price)
            self.cash -= fill.quantity * fill.price
        else:
            position.decrease(-fill.quantity, fill.price)
            self.cash += -fill.quantity * fill.price

    def set_target(
        self,
        symbol: str,
        target_quantity: float,
        price: float,
    ) -> None:
        position = self.holdings.get_position(symbol)
        current_quantity = position.quantity
        
        delta = target_quantity - current_quantity
        
        if delta > 0:
            position.increase(delta, price)
            self.cash -= delta * price
        elif delta < 0:
            position.decrease(-delta, price)
            self.cash += -delta * price

    def market_value(self, prices: Dict[str, float]) -> float:
        value = 0.0
        for symbol, position in self.holdings.positions.items():
            value += position.quantity * prices.get(symbol, 0.0)
        return value

    def equity(self, prices: Dict[str, float]) -> float:
        return self.cash + self.market_value(prices)

    def update_equity_curve(self, timestamp: datetime, prices: Dict[str, float]) -> None:
        self.equity_curve.append((timestamp, self.equity(prices)))