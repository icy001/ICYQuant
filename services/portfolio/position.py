"""
Portfolio position snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PortfolioPosition:
    symbol: str
    quantity: Decimal
    market_value: Decimal