"""
Portfolio optimizer.
"""

from __future__ import annotations

from .allocation import Allocation


class PortfolioOptimizer:
    def optimize(
        self,
        strategies,
    ):
        total = sum(s.sharpe for s in strategies)

        allocations = []

        for strategy in strategies:
            weight = strategy.sharpe / total

            allocations.append(
                Allocation(
                    strategy_id=strategy.strategy_id,
                    weight=weight,
                )
            )

        return allocations