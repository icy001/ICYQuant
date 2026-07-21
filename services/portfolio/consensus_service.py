"""
Consensus service.
"""


class PortfolioConsensusService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def execute(
        self,
        *args,
        **kwargs,
    ):

        return self.engine.execute(
            *args,
            **kwargs,
        )