"""OrderType enum."""
from __future__ import annotations

from enum import Enum, auto


class OrderType(Enum):
    MARKET = auto()
    LIMIT = auto()
    STOP = auto()
    STOP_LIMIT = auto()
    TWAP = auto()
    VWAP = auto()
    ICEBERG = auto()

    @property
    def label(self) -> str:
        _labels = {
            OrderType.MARKET: "Market",
            OrderType.LIMIT: "Limit",
            OrderType.STOP: "Stop",
            OrderType.STOP_LIMIT: "Stop Limit",
            OrderType.TWAP: "TWAP",
            OrderType.VWAP: "VWAP",
            OrderType.ICEBERG: "Iceberg",
        }
        return _labels[self]

    @property
    def requires_price(self) -> bool:
        return self in (
            OrderType.LIMIT,
            OrderType.STOP_LIMIT,
        )

    @property
    def is_algo(self) -> bool:
        return self in (
            OrderType.TWAP,
            OrderType.VWAP,
            OrderType.ICEBERG,
        )
