"""
Event service.
"""


class PortfolioEventService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def record(
        self,
        *args,
        **kwargs,
    ):

        return self.engine.record(
            *args,
            **kwargs,
        )