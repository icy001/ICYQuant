"""Investment committee service — top-level entry point."""

from __future__ import annotations

from .voting import VotingSystem


class InvestmentCommitteeService:
    """Top-level service for the AI Autonomous Investment Committee.

    Accepts committee opinions, delegates to the voting system, and
    returns the final investment decision.
    """

    def __init__(self, voting: VotingSystem) -> None:
        self.voting = voting

    def decide(self, opinions: list[str]) -> dict:
        """Convene the committee and produce a decision.

        Args:
            opinions: List of member vote strings.

        Returns:
            Dict with the final committee decision.
        """
        return self.voting.vote(opinions)
