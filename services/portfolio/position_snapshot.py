"""
Portfolio position snapshot.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PositionSnapshot:
    symbol: str
    quantity: Decimal
    average_price: Decimal
    market_value: Decimal