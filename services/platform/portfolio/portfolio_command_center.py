"""
Portfolio command center.
"""


class PortfolioCommandCenter:

    def __init__(
        self,
        allocation,
        optimizer,
        rebalance,
    ):

        self.allocation = allocation

        self.optimizer = optimizer

        self.rebalance = rebalance

    def execute(
        self,
        assets,
    ):

        allocation = self.allocation.allocate(
            assets,
            {}
        )

        optimized = self.optimizer.optimize(
            allocation
        )

        return self.rebalance.rebalance(
            {},
            optimized
        )