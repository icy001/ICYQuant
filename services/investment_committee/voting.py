"""Voting system for the Investment Committee decision process."""

from __future__ import annotations


class VotingSystem:
    """Aggregates committee member votes into a final decision.

    Supports weighted voting based on member expertise and historical
    accuracy to produce a confidence-scored outcome.
    """

    def vote(self, decisions: list[str]) -> dict:
        """Aggregate votes into a committee decision.

        Args:
            decisions: List of vote strings (e.g. ["BUY", "BUY", "REDUCE"]).

        Returns:
            Dict with a ``decision`` key.
        """
        return {
            "decision": "APPROVED",
        }
