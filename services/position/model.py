"""
Position domain model.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Position:
    account_id: str
    symbol: str
    quantity: Decimal = Decimal("0")
    average_cost: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    side: str = "FLAT"
    version: int = 1