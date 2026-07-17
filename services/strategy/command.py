"""
Strategy order command.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class OrderCommand:
    strategy_id: str
    symbol: str
    side: str
    quantity: Decimal