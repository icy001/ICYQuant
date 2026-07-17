"""
Position sizing result.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PositionSizeResult:
    quantity: Decimal
    risk_amount: Decimal
    approved: bool