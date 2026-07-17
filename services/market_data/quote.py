"""
Level-1 market quote.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime


@dataclass(frozen=True)
class Quote:
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    timestamp: datetime