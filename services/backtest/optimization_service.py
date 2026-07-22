"""
Optimization service.
"""


class OptimizationService:

    def __init__(
        self,
        runner,
    ):

        self.runner = runner


    def evaluate(
        self,
        parameters,
        score,
    ):

        return self.runner.evaluate(
            parameters,
            score,
        )