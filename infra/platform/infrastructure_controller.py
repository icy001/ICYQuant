"""
ICYQuant infrastructure controller.
"""


class InfrastructureController:

    def __init__(
        self,
        monitor,
        failover,
    ):
        self.monitor = monitor
        self.failover = failover

    def health_check(self):
        return self.monitor.collect()