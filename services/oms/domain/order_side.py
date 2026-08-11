"""OrderSide enum — BUY / SELL."""
from __future__ import annotations

from enum import Enum, auto


class OrderSide(Enum):
    BUY = auto()
    SELL = auto()

    @property
    def label(self) -> str:
        return "Buy" if self == OrderSide.BUY else "Sell"

    @property
    def is_buy(self) -> bool:
        return self == OrderSide.BUY

    @property
    def opposite(self) -> "OrderSide":
        return OrderSide.SELL if self == OrderSide.BUY else OrderSide.BUY
