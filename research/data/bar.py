from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Bar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def typical_price(self) -> float:
        return (self.high + self.low + self.close) / 3

    def is_bullish(self) -> bool:
        return self.close > self.open

    def is_bearish(self) -> bool:
        return self.close < self.open

    def range(self) -> float:
        return self.high - self.low

    def body_range(self) -> float:
        return abs(self.close - self.open)

    def upper_wick(self) -> float:
        if self.is_bullish():
            return self.high - self.close
        return self.high - self.open

    def lower_wick(self) -> float:
        if self.is_bullish():
            return self.open - self.low
        return self.close - self.low