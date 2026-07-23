"""
Alert rule definition.
"""


class AlertRule:

    def __init__(
        self,
        metric,
        threshold,
    ):
        self.metric = metric

        self.threshold = threshold