"""
Scenario analysis service.
"""


class ScenarioService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def analyze(
        self,
        scenario_id,
        portfolio,
    ):

        return self.engine.analyze(
            scenario_id,
            portfolio,
        )