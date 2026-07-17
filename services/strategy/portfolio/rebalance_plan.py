"""
Rebalance action.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RebalancePlan:
    symbol: str
    action: str
    quantity: Decimal
    estimated_cost: Decimal