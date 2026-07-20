"""
Portfolio rebalance calculator.
"""


class RebalanceCalculator:
    def calculate(
        self,
        current,
        target,
    ):
        return target - current