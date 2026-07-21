"""
Observability service.
"""


class ObservabilityService:

    def __init__(
        self,
        telemetry,
    ):

        self.telemetry = telemetry

    def report(
        self,
        payload,
    ):

        return self.telemetry.publish(
            payload,
        )