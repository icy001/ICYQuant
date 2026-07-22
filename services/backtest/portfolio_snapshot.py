"""
Portfolio snapshot model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PortfolioSnapshot:

    timestamp: datetime

    cash: float

    market_value: float

    equity: float

    nav: float