"""
Portfolio performance snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PerformanceSnapshot:
    total_return: Decimal
    cumulative_return: Decimal
    max_drawdown: Decimal
    volatility: Decimal
    sharpe_ratio: Decimal