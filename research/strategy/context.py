from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict


@dataclass
class StrategyContext:
    symbol: str
    initial_capital: float = 100000.0
    cash: float = field(default=100000.0)
    positions: Dict[str, float] = field(default_factory=dict)
    current_time: datetime = None
    parameters: Dict = field(default_factory=dict)
    indicators: Dict = field(default_factory=dict)
    signals: Dict = field(default_factory=dict)

    def __post_init__(self):
        if self.cash == 100000.0 and self.initial_capital != 100000.0:
            self.cash = self.initial_capital

    def update_position(self, symbol: str, quantity: float):
        if symbol in self.positions:
            self.positions[symbol] += quantity
        else:
            self.positions[symbol] = quantity

    def get_position(self, symbol: str) -> float:
        return self.positions.get(symbol, 0.0)

    def update_cash(self, amount: float):
        self.cash += amount