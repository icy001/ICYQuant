"""
Portfolio state context.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PortfolioContext:
    equity: Decimal
    current_exposure: Decimal
    daily_loss: Decimal
    max_drawdown: Decimal