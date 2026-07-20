"""
Portfolio service.
"""


class PortfolioService:
    def __init__(
        self,
        repository,
    ):
        self.repository = repository

    def create(
        self,
        portfolio,
    ):
        self.repository.save(portfolio)
        return portfolio