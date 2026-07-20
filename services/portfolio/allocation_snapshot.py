"""
Allocation snapshot.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AllocationSnapshot:
    asset_class: str
    current_weight: Decimal
    target_weight: Decimal