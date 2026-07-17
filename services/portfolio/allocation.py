"""
Portfolio allocation models.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Allocation:
    symbol: str
    target_weight: Decimal
    current_weight: Decimal