"""
Portfolio position model.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Position:
    symbol: str
    quantity: Decimal
    average_price: Decimal