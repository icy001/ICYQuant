"""
Dynamic rebalance controller.
"""

from __future__ import annotations


class RebalanceController:
    def need_rebalance(
        self,
        current,
        target,
        threshold,
    ):
        diff = abs(current - target)

        return diff > threshold