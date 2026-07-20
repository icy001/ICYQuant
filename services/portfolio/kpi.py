"""
Portfolio KPI models.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PortfolioKPI:
    nav: Decimal
    return_rate: Decimal
    risk: Decimal
    sharpe: Decimal