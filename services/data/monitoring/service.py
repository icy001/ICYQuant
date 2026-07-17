"""
Monitoring service.
"""


class MonitoringService:
    def __init__(
        self,
        monitor,
        detector,
    ):
        self.monitor = monitor
        self.detector = detector