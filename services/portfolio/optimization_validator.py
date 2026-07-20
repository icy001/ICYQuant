"""
Optimization validation.
"""


class OptimizationValidator:
    def validate(
        self,
        weights,
    ):
        return round(sum(weights.values()), 6) == 1