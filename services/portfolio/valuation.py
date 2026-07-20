"""
Portfolio valuation model.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ValuationResult:
    symbol: str
    market_value: Decimal
    unrealized_pnl: Decimal