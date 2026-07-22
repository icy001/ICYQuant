"""
Scenario analysis engine.
"""

from .scenario_report import ScenarioReport


class ScenarioEngine:

    def __init__(
        self,
        repository,
        calculator,
    ):

        self.repository = repository

        self.calculator = calculator

    def analyze(
        self,
        scenario_id,
        portfolio,
    ):

        scenario = self.repository.load(
            scenario_id
        )

        result = self.calculator.calculate(
            portfolio,
            scenario,
        )

        before = sum(
            portfolio.values()
        )
        after = sum(
            result.values()
        )

        return ScenarioReport(
            scenario_id,
            before,
            after,
            after - before,
        )