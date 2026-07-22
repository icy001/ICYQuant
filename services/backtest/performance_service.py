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
        *args,
        **kwargs,
    ):

        return self.engine.analyze(
            *args,
            **kwargs,
        )