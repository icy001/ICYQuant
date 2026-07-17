"""
Strategy governance rules.
"""

from __future__ import annotations


class StrategyGovernance:
    def evaluate(
        self,
        sharpe,
        drawdown,
    ):
        if sharpe < 0.5:
            return "DEGRADE"

        if drawdown > 0.2:
            return "SUSPEND"

        return "KEEP"