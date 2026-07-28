"""Research task planner for decomposing research topics."""

from __future__ import annotations


class ResearchTaskPlanner:
    """Plans and decomposes a research topic into sub-tasks.

    Maps a high-level topic (e.g. "NVDA") to an ordered sequence of
    analysis steps required to produce a complete investment thesis.
    """

    def plan(self, topic: str) -> list[str]:
        """Decompose a research topic into analysis steps.

        Args:
            topic: The research topic (e.g. company ticker or theme).

        Returns:
            Ordered list of analysis modules to execute.
        """
        return [
            "financial",
            "industry",
            "valuation",
            "risk",
        ]
