"""
Strategy ranking.
"""

from __future__ import annotations


class StrategyRanker:
    def rank(
        self,
        strategies,
    ):
        return sorted(
            strategies,
            key=lambda x: x.sharpe,
            reverse=True,
        )