"""
Alert rules.
"""


class AlertRule:

    def evaluate(
        self,
        value,
        threshold,
    ):

        return value >= threshold