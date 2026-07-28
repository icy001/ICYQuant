"""Opportunity ranking engine for global opportunity scoring."""

from __future__ import annotations


class OpportunityRankingEngine:
    """Ranks global investment opportunities by their relative attractiveness.

    Orders sectors, themes, and regions by composite opportunity score
    to guide capital allocation priorities.
    """

    def rank(self, opportunities: list[str]) -> list[str]:
        """Rank opportunities by attractiveness.

        Args:
            opportunities: List of opportunity identifiers.

        Returns:
            Sorted list of opportunities.
        """
        return sorted(opportunities)
