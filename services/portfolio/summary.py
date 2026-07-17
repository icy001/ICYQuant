"""
Portfolio summary model.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PortfolioSummary:
    account_id: str
    nav: Decimal
    total_pnl: Decimal
    total_return: Decimal