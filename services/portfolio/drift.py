"""
Portfolio drift detector.
"""

from decimal import Decimal


class DriftDetector:
    def calculate(
        self,
        current,
        target,
    ):
        return target - current

    def exceed_threshold(
        self,
        drift,
        threshold,
    ):
        return abs(drift) >= threshold