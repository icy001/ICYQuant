"""
Alpha research laboratory.
"""


class AlphaResearchLab:

    def __init__(
        self,
        factor_engine,
        alpha_engine,
        evaluator,
    ):

        self.factor_engine = factor_engine

        self.alpha_engine = alpha_engine

        self.evaluator = evaluator

    def run(
        self,
        data,
    ):

        factors = self.factor_engine.research()

        alpha = self.alpha_engine.discover(
            factors
        )

        return self.evaluator.evaluate(
            alpha
        )