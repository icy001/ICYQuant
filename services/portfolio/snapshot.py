"""
Portfolio valuation snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PortfolioSnapshot:
    market_value: Decimal
    cash_value: Decimal
    gross_asset_value: Decimal
    net_asset_value: Decimal