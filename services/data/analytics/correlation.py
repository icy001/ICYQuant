"""
Factor correlation analysis.
"""


class FactorCorrelation:
    def calculate(
        self,
        factor_a,
        factor_b,
    ):
        if len(factor_a) != len(factor_b):
            return 0

        return sum(a * b for a, b in zip(factor_a, factor_b))