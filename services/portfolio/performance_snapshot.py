"""
Performance snapshot.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PerformanceSnapshot:
    total_return: Decimal
    alpha: Decimal
    beta: Decimal