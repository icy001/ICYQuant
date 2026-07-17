"""
Factor health scoring.
"""


class FactorHealth:
    def score(
        self,
        ic,
        decay,
        turnover,
    ):
        return ic - abs(decay) - turnover