"""
Portfolio repository.
"""


class PortfolioRepository:
    def __init__(self):
        self.storage = {}

    def save(
        self,
        portfolio,
    ):
        self.storage[portfolio.portfolio_id] = portfolio

    def get(
        self,
        portfolio_id,
    ):
        return self.storage.get(portfolio_id)