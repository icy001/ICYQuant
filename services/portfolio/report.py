"""
Portfolio report model.
"""

from __future__ import annotations

from dataclasses import dataclass

from .analytics_snapshot import PortfolioAnalyticsSnapshot
from .summary import PortfolioSummary


@dataclass(frozen=True)
class PortfolioReport:
    summary: PortfolioSummary
    analytics: PortfolioAnalyticsSnapshot