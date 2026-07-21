"""
Portfolio snapshot models.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class PortfolioSnapshot:

    snapshot_id: str

    portfolio_id: str

    created_at: datetime

    data: dict


@dataclass(frozen=True)
class ValuationSnapshot:
    market_value: Decimal
    cash_value: Decimal
    gross_asset_value: Decimal
    net_asset_value: Decimal