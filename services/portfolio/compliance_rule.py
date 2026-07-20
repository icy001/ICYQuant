"""
Compliance rule definition.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PortfolioLimitRule:
    asset: str
    max_weight: Decimal