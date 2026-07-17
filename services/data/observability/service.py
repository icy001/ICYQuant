"""
Observability service.
"""


class ObservabilityService:
    def __init__(
        self,
        dashboard,
        alert_center,
    ):
        self.dashboard = dashboard
        self.alert_center = alert_center