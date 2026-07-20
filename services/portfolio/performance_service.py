"""
Performance service.
"""


class PerformanceService:
    def __init__(
        self,
        engine,
    ):
        self.engine = engine

    def analyze(
        self,
        strategies,
    ):
        return self.engine.analyze(strategies)