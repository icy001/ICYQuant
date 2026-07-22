"""
Stress scenario repository.
"""


class StressScenarioRepository:

    def __init__(self):

        self.scenarios = {}

    def save(
        self,
        scenario,
    ):

        self.scenarios[
            scenario.scenario_id
        ] = scenario

    def load(
        self,
        scenario_id,
    ):

        return self.scenarios.get(
            scenario_id
        )

    def list_all(self):

        return list(
            self.scenarios.values()
        )