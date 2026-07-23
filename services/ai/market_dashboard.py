"""
AI market dashboard data provider.
"""


class MarketDashboard:

    def __init__(
        self,
    ):

        self.metrics = {}

    def update(
        self,
        key,
        value,
    ):

        self.metrics[key] = value

    def snapshot(self):

        return self.metrics