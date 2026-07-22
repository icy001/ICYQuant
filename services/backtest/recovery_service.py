"""
Recovery service.
"""


class RecoveryService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def recover(
        self,
        context,
    ):

        return self.engine.recover(
            context
        )