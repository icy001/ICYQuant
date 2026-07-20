"""
Portfolio exposure calculator.
"""


class ExposureCalculator:
    def calculate(
        self,
        snapshots,
    ):
        return sum(position.market_value for position in snapshots)