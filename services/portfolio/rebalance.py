"""
Rebalance models.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RebalanceRequest:
    asset: str
    current_weight: Decimal
    target_weight: Decimal
    delta: Decimal


class RebalanceCalculator:
    def calculate(
        self,
        current,
        target,
    ):
        return target - current