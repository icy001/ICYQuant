"""
Portfolio optimizer.
"""


class PortfolioOptimizer:
    def optimize(
        self,
        assets,
        objective,
    ):
        weight = 1 / len(assets)
        return {asset: weight for asset in assets}