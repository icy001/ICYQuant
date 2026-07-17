"""
Tick market data.
"""

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime


@dataclass(frozen=True)
class Tick:
    symbol: str
    price: Decimal
    volume: Decimal
    timestamp: datetime