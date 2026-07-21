"""
Portfolio version engine.
"""

from datetime import datetime

from .version import PortfolioVersion


class PortfolioVersionEngine:
    def __init__(
        self,
        repository,
    ):
        self.repository = repository

    def create(
        self,
        version_id,
        portfolio_id,
        snapshot,
    ):
        version = PortfolioVersion(
            version_id=version_id,
            portfolio_id=portfolio_id,
            created_at=datetime.utcnow(),
            snapshot=snapshot,
        )

        self.repository.save(version)

        return version