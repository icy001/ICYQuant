"""
Walk forward service.
"""


class WalkForwardService:
    def __init__(
        self,
        engine,
    ):
        self.engine = engine

    def analyze(
        self,
        strategy,
        dataset,
    ):
        return self.engine.run(strategy, dataset)