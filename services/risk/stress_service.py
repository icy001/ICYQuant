"""
Stress testing service.
"""


class StressService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def run(
        self,
        scenario_id,
        portfolio,
    ):

        return self.engine.run(
            scenario_id,
            portfolio,
        )