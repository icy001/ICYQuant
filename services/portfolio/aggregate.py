"""
Portfolio aggregate root.
"""


class PortfolioAggregate:
    def __init__(
        self,
        portfolio,
    ):
        self.portfolio = portfolio

    def activate(self):
        self.portfolio.status = "ACTIVE"

    def close(self):
        self.portfolio.status = "CLOSED"