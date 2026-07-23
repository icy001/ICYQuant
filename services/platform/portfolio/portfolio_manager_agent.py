"""
AI Portfolio Manager Agent.
"""


class PortfolioManagerAgent:

    def __init__(
        self,
        optimizer,
    ):

        self.optimizer = optimizer

    def manage(
        self,
        portfolio,
    ):

        return self.optimizer.optimize(
            portfolio
        )