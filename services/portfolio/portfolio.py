from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Portfolio:
    cash: float = 0.0
    positions: Dict[str, float] = field(default_factory=dict)
    market_prices: Dict[str, float] = field(default_factory=dict)

    def get_position(self, symbol: str) -> float:
        return self.positions.get(symbol, 0.0)

    def set_position(self, symbol: str, quantity: float) -> None:
        self.positions[symbol] = quantity

    def update_position(self, symbol: str, delta: float) -> None:
        self.positions[symbol] = self.positions.get(symbol, 0.0) + delta

    def get_position_value(self, symbol: str) -> float:
        return self.positions.get(symbol, 0.0) * self.market_prices.get(symbol, 0.0)

    def get_total_position_value(self) -> float:
        return sum(
            self.positions.get(symbol, 0.0) * self.market_prices.get(symbol, 0.0)
            for symbol in self.positions
        )

    def get_total_value(self) -> float:
        return self.cash + self.get_total_position_value()

    def get_exposure(self) -> float:
        total_value = self.get_total_value()
        if total_value == 0:
            return 0.0
        return self.get_total_position_value() / total_value

    def to_dict(self) -> Dict:
        return {
            "cash": self.cash,
            "positions": self.positions,
            "total_value": self.get_total_value(),
            "exposure": self.get_exposure(),
        }
