"""
Risk metric repository.
"""


class RiskMetricRepository:

    def __init__(self):

        self.metrics = []

    def save(
        self,
        metric,
    ):

        self.metrics.append(
            metric
        )

    def list_all(self):

        return self.metrics