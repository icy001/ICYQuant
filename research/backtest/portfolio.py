from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Tuple


@dataclass
class Portfolio:
    initial_capital: float
    cash: float
    positions: Dict[str, float] = field(default_factory=dict)
    equity_curve: List[Tuple[datetime, float]] = field(default_factory=list)

    def update_fill(self, fill) -> None:
        self.cash += fill.cash_change
        
        if fill.symbol not in self.positions:
            self.positions[fill.symbol] = 0.0
        
        if fill.side == "BUY":
            self.positions[fill.symbol] += fill.quantity
        else:
            self.positions[fill.symbol] -= fill.quantity

    def update_market_value(self, timestamp: datetime, price_map: Dict[str, float]) -> None:
        market_value = sum(
            qty * price_map.get(symbol, 0.0)
            for symbol, qty in self.positions.items()
        )
        equity = self.cash + market_value
        self.equity_curve.append((timestamp, equity))

    def get_market_value(self, price_map: Dict[str, float]) -> float:
        return sum(
            qty * price_map.get(symbol, 0.0)
            for symbol, qty in self.positions.items()
        )

    def get_equity(self, price_map: Dict[str, float]) -> float:
        return self.cash + self.get_market_value(price_map)

    def get_pnl(self, price_map: Dict[str, float]) -> float:
        return self.get_equity(price_map) - self.initial_capital

    def apply_fill(self, fill) -> None:
        cash_change = -fill.quantity * fill.price
        
        self.cash += cash_change
        
        if fill.symbol not in self.positions:
            self.positions[fill.symbol] = 0.0
        
        self.positions[fill.symbol] += fill.quantity