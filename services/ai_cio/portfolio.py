"""Portfolio construction engine for building investable portfolios."""

from __future__ import annotations


class PortfolioConstructionEngine:
    """Builds investable portfolios from strategic asset allocations.

    Supports equal weight, risk parity, factor allocation, and
    optimization-based construction approaches.
    """

    def construct(self, allocation: dict) -> dict:
        """Construct a portfolio from a target allocation.

        Args:
            allocation: Target asset allocation dict.

        Returns:
            The constructed portfolio.
        """
        return allocation
