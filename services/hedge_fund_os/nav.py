"""NAV engine for daily net asset value calculation."""

from __future__ import annotations


class NAVEngine:
    """Core engine for calculating Net Asset Value.

    Computes daily, intraday, and strategy-level NAV from assets
    and liabilities across all fund accounts.
    """

    def calculate(self, assets: float, liabilities: float) -> float:
        """Calculate Net Asset Value.

        Args:
            assets: Total fund assets.
            liabilities: Total fund liabilities.

        Returns:
            NAV = assets - liabilities.
        """
        return assets - liabilities
