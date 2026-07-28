"""Portfolio manager agent for capital allocation review."""

from __future__ import annotations


class PortfolioManagerAgent:
    """Simulates a portfolio manager reviewing investment proposals.

    Considers portfolio impact, capital allocation, and opportunity
    cost to recommend position sizing.
    """

    def review(self, proposal: dict) -> dict:
        """Review a proposal from a portfolio perspective.

        Args:
            proposal: The investment proposal.

        Returns:
            Dict with an ``allocation`` recommendation (fraction of AUM).
        """
        return {
            "allocation": 0.05,
        }
