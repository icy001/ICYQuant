"""
Portfolio snapshot engine.
"""

from datetime import datetime

from .snapshot import PortfolioSnapshot


class PortfolioSnapshotEngine:

    def __init__(
        self,
        repository,
    ):

        self.repository = repository

    def create(
        self,
        snapshot_id,
        portfolio_id,
        data,
    ):

        snapshot = PortfolioSnapshot(
            snapshot_id=snapshot_id,
            portfolio_id=portfolio_id,
            created_at=datetime.utcnow(),
            data=data,
        )

        self.repository.save(
            snapshot
        )

        return snapshot