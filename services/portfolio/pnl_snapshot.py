"""
Portfolio PnL snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PortfolioPnLSnapshot:
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    total_pnl: Decimal