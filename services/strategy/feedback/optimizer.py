"""
Feedback optimizer.
"""

from __future__ import annotations


class FeedbackOptimizer:
    def adjust_weight(
        self,
        score,
    ):
        if score.sharpe >= 2:
            return 1.2

        if score.sharpe < 1:
            return 0.8

        return 1.0