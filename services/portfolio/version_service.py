"""
Version service.
"""


class PortfolioVersionService:
    def __init__(
        self,
        engine,
    ):
        self.engine = engine

    def create(
        self,
        version_id,
        portfolio_id,
        snapshot,
    ):
        return self.engine.create(version_id, portfolio_id, snapshot)