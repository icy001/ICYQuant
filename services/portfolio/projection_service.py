"""
Projection service.
"""


class PortfolioProjectionService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def project(
        self,
        portfolio_id,
        state,
    ):

        return self.engine.project(
            portfolio_id,
            state,
        )