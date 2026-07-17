"""
Factor evaluator.
"""

from .ic import InformationCoefficient


class FactorEvaluator:
    def __init__(self):
        self.ic = InformationCoefficient()

    def evaluate(
        self,
        factor,
        returns,
    ):
        return self.ic.calculate(factor, returns)