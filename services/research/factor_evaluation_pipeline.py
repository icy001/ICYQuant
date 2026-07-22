"""
Factor evaluation pipeline.
"""


class FactorEvaluationPipeline:

    def __init__(
        self,
        calculator,
        ic,
        rank_ic,
    ):

        self.calculator = calculator

        self.ic = ic

        self.rank_ic = rank_ic

    def evaluate(
        self,
        factor,
        dataset,
        returns,
    ):

        result = self.calculator.calculate(
            factor,
            dataset,
        )

        values = result["values"]

        return {
            "factor":
                factor.name,
            "ic":
                self.ic.analyze(
                    values,
                    returns,
                ),
            "rank_ic":
                self.rank_ic.analyze(
                    sorted(values),
                    sorted(returns),
                ),
        }