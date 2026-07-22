"""
Risk monitoring service.
"""


class RiskMonitoringService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def process(
        self,
        *args,
        **kwargs,
    ):

        return self.engine.process(
            *args,
            **kwargs,
        )