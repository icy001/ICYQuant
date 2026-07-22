"""
Scenario impact calculator.
"""


class ScenarioCalculator:

    def calculate(
        self,
        portfolio,
        scenario,
    ):

        result = {}

        for asset, value in portfolio.items():

            shock = scenario.factors.get(
                asset,
                0,
            )
            result[asset] = value * (
                1 + shock
            )

        return result