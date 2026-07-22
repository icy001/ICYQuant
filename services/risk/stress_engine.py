"""
Stress testing engine.
"""

from .stress_result import StressResult


class StressEngine:

    def __init__(
        self,
        repository,
        calculator,
    ):

        self.repository = repository

        self.calculator = calculator

    def run(
        self,
        scenario_id,
        portfolio,
    ):

        scenario = self.repository.load(
            scenario_id
        )

        stressed = self.calculator.calculate(
            portfolio,
            scenario,
        )

        before = sum(
            portfolio.values()
        )
        after = sum(
            stressed.values()
        )

        return StressResult(
            scenario_id,
            before,
            after,
            after - before,
        )