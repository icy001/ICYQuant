"""
Performance metrics.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PerformanceMetric:
    total_return: Decimal
    win_rate: Decimal
    sharpe_ratio: Decimal