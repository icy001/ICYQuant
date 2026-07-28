"""Hedge Fund OS service — top-level entry point for fund operations."""

from __future__ import annotations

from .nav import NAVEngine


class HedgeFundOSService:
    """Top-level service for the AI Autonomous Hedge Fund Operating System.

    Provides the primary API for fund operations including NAV
    calculation, capital management, and reporting.
    """

    def __init__(self, nav_engine: NAVEngine) -> None:
        self.nav_engine = nav_engine

    def nav(self, assets: float, liabilities: float) -> float:
        """Calculate the fund's Net Asset Value.

        Args:
            assets: Total fund assets.
            liabilities: Total fund liabilities.

        Returns:
            NAV = assets - liabilities.
        """
        return self.nav_engine.calculate(assets, liabilities)
