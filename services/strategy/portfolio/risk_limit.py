"""
Portfolio risk limits.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RiskLimit:
    max_exposure: Decimal
    max_daily_loss: Decimal
    max_drawdown: Decimal