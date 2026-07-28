"""Bull case agent for building the long-side argument."""

from __future__ import annotations


class BullAgent:
    """Builds the bull case for an investment proposal.

    Analyzes growth catalysts, competitive advantages, and market
    opportunities to construct a compelling buy argument.
    """

    def analyze(self, proposal: dict) -> dict:
        """Analyze a proposal from a bull perspective.

        Args:
            proposal: The investment proposal to analyze.

        Returns:
            Dict with ``side`` and ``reason`` keys.
        """
        return {
            "side": "BUY",
            "reason": "growth",
        }
