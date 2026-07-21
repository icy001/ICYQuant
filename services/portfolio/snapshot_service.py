"""
Snapshot service.
"""


class PortfolioSnapshotService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def create(
        self,
        snapshot_id,
        portfolio_id,
        data,
    ):

        return self.engine.create(
            snapshot_id,
            portfolio_id,
            data,
        )