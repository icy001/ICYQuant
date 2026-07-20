"""
Risk metrics.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RiskMetric:
    var: Decimal
    volatility: Decimal
    drawdown: Decimal