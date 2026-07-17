"""
Unified portfolio analytics snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass

from .performance_snapshot import PerformanceSnapshot
from .pnl_snapshot import PortfolioPnLSnapshot
from .snapshot import PortfolioSnapshot


@dataclass(frozen=True)
class PortfolioAnalyticsSnapshot:
    valuation: PortfolioSnapshot
    pnl: PortfolioPnLSnapshot
    performance: PerformanceSnapshot