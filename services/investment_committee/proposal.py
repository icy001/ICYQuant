"""Investment proposal engine for formalizing research output."""

from __future__ import annotations


class InvestmentProposal:
    """Creates a structured investment proposal from a research thesis.

    The proposal is the formal document presented to the Investment
    Committee for review, debate, and decision.
    """

    def create(self, symbol: str, thesis: dict) -> dict:
        """Create an investment proposal.

        Args:
            symbol: Ticker symbol.
            thesis: Investment thesis from the research platform.

        Returns:
            Dict with ``symbol`` and ``thesis`` keys.
        """
        return {
            "symbol": symbol,
            "thesis": thesis,
        }
