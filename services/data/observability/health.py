"""
Dataset health score.
"""


class HealthCalculator:
    def calculate(
        self,
        quality,
        freshness,
    ):
        return (quality + freshness) / 2