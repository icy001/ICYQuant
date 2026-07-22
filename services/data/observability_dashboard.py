"""
Observability dashboard.
"""


class ObservabilityDashboard:

    def snapshot(
        self,
        health,
        latency,
        freshness,
        quality,
    ):

        return {
            "health": health,
            "latency": latency,
            "freshness": freshness,
            "quality": quality,
        }