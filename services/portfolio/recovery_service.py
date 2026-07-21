"""
Recovery service.
"""


class PortfolioRecoveryService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def recover(
        self,
        recovery_id,
        snapshot,
    ):

        return self.engine.recover(
            recovery_id,
            snapshot,
        )