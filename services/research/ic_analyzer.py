"""
Information Coefficient analyzer.
"""

from statistics import mean


class ICAnalyzer:

    def analyze(
        self,
        factor_values,
        returns,
    ):

        n = len(factor_values)
        if n != len(returns) or n == 0:
            return 0.0

        mean_f = mean(factor_values)
        mean_r = mean(returns)

        numerator = sum(
            (f - mean_f) * (r - mean_r)
            for f, r in zip(factor_values, returns)
        )

        denom_f = sum((f - mean_f) ** 2 for f in factor_values) ** 0.5
        denom_r = sum((r - mean_r) ** 2 for r in returns) ** 0.5

        if denom_f == 0 or denom_r == 0:
            return 0.0

        return numerator / (denom_f * denom_r)