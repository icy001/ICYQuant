"""
Rebalance policy.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RebalancePolicy:
    threshold: Decimal