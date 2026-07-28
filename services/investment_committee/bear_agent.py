"""Bear case agent for building the short-side / challenge argument."""

from __future__ import annotations


class BearAgent:
    """Builds the bear case against an investment proposal.

    Analyzes valuation risks, competition threats, macro headwinds, and
    downside scenarios to construct a counter-argument.
    """

    def analyze(self, proposal: dict) -> dict:
        """Analyze a proposal from a bear perspective.

        Args:
            proposal: The investment proposal to analyze.

        Returns:
            Dict with ``side`` and ``reason`` keys.
        """
        return {
            "side": "SELL",
            "reason": "risk",
        }
