"""
Real-time risk monitor.
"""


class RealTimeRiskMonitor:

    def __init__(
        self,
        alert_engine,
    ):

        self.alert_engine = alert_engine

    def check(
        self,
        value,
        threshold,
    ):

        return self.alert_engine.evaluate(
            value,
            threshold,
        )