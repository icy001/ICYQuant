"""
Portfolio constraints.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AllocationConstraint:
    asset_class: str
    min_weight: Decimal
    max_weight: Decimal