"""
Portfolio facade.
"""

from __future__ import annotations

from .analytics import PortfolioAnalyticsService


class PortfolioFacade:
    def __init__(self):
        self.analytics = PortfolioAnalyticsService()