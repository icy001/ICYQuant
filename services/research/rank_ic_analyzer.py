"""
Rank IC analyzer.
"""

from statistics import mean


class RankICAnalyzer:

    def analyze(
        self,
        factor_rank,
        return_rank,
    ):

        n = len(factor_rank)
        if n != len(return_rank) or n == 0:
            return 0.0

        mean_f = mean(factor_rank)
        mean_r = mean(return_rank)

        numerator = sum(
            (f - mean_f) * (r - mean_r)
            for f, r in zip(factor_rank, return_rank)
        )

        denom_f = sum((f - mean_f) ** 2 for f in factor_rank) ** 0.5
        denom_r = sum((r - mean_r) ** 2 for r in return_rank) ** 0.5

        if denom_f == 0 or denom_r == 0:
            return 0.0

        return numerator / (denom_f * denom_r)