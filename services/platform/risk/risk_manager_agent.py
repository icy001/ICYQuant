"""
AI Risk Manager Agent.
"""


class RiskManagerAgent:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def review(
        self,
        portfolio,
    ):

        return self.engine.calculate(
            portfolio
        )