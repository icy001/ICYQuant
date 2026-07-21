"""
Portfolio metrics.
"""


class PortfolioMetrics:

    def collect(
        self,
        name,
        value,
    ):

        return {
            "metric": name,
            "value": value,
        }