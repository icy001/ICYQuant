"""
Factor combination.
"""


class FactorCombination:
    def combine(
        self,
        factors,
        weights,
    ):
        score = 0

        for factor, weight in zip(factors, weights):
            score += factor * weight

        return score