"""
Pre-trade risk service.
"""


class PreTradeRiskService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def execute(
        self,
        request,
    ):

        return self.engine.check(
            request,
        )