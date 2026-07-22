"""
Real-time risk monitoring engine.
"""


class RiskMonitoringEngine:

    def __init__(
        self,
        monitor,
        notifier,
    ):

        self.monitor = monitor

        self.notifier = notifier

    def process(
        self,
        value,
        threshold,
        message,
    ):

        level = self.monitor.check(
            value,
            threshold,
        )

        return self.notifier.notify(
            level,
            message,
        )