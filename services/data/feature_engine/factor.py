"""
Factor calculator.
"""

from __future__ import annotations


class FactorCalculator:
    def value_factor(
        self,
        price,
        earnings,
    ):
        if earnings == 0:
            return 0

        return price / earnings

    def growth_factor(
        self,
        current,
        previous,
    ):
        return (current - previous) / previous