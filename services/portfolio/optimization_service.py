"""
Optimization service.
"""


class OptimizationService:
    def __init__(
        self,
        engine,
    ):
        self.engine = engine

    def optimize(
        self,
        assets,
        objective,
    ):
        return self.engine.run(assets, objective)