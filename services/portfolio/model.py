"""
Portfolio aggregate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .cash import CashBalance
from .enums import PortfolioStatus
from .position import PortfolioPosition


@dataclass
class Portfolio:
    account_id: str
    status: PortfolioStatus
    cash: CashBalance
    positions: list[PortfolioPosition] = field(default_factory=list)