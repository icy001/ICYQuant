"""
Factor ranking.
"""


class FactorRanker:
    def rank(
        self,
        factors,
    ):
        return sorted(factors, key=lambda x: x["ic"], reverse=True)