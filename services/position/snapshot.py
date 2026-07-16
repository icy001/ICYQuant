"""
Position snapshot model.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PositionSnapshot:
    account_id: str
    symbol: str
    quantity: Decimal
    average_cost: Decimal
    realized_pnl: Decimal