"""Investment thesis engine for building bull/base/bear cases."""

from __future__ import annotations


class InvestmentThesisEngine:
    """Synthesizes research data into a structured investment thesis.

    Generates bull, base, and bear case scenarios based on aggregated
    financial, industry, and valuation analysis.
    """

    def build(self, data: dict) -> dict:
        """Build an investment thesis from research data.

        Args:
            data: Aggregated research results.

        Returns:
            Dict with a ``thesis`` key containing the structured thesis.
        """
        return {
            "thesis": data,
        }
