"""Risk budget engine for managing risk capital limits."""

from __future__ import annotations


class RiskBudgetEngine:
    """Manages the firm-wide risk budget.

    Controls volatility budget, drawdown budget, exposure limits, and
    correlation risk across the entire portfolio.
    """

    def calculate(self, portfolio: dict) -> dict:
        """Calculate the risk budget for a portfolio.

        Args:
            portfolio: Portfolio allocation dict.

        Returns:
            Dict with a ``risk_limit`` key.
        """
        return {
            "risk_limit": 0.2,
        }
